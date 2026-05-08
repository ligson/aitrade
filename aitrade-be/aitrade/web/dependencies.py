from fastapi import Depends
from fastapi import Header
from fastapi import Request

from ..config.config_file import Config
from ..db import UserModel
from ..db.session import get_session_factory
from .exceptions import ForbiddenError
from .exceptions import UnauthorizedError
from .security import parse_token


def get_config(request: Request) -> Config:
    return request.app.state.app_config


def get_current_user(
    authorization: str | None = Header(default=None),
    config: Config = Depends(get_config),
) -> dict:
    if not authorization or not authorization.startswith('Bearer '):
        raise UnauthorizedError('缺少有效的 Authorization Bearer Token')
    token = authorization.split(' ', 1)[1].strip()
    if not token:
        raise UnauthorizedError('缺少有效的 Authorization Bearer Token')
    try:
        username = parse_token(token, config.web_jwt_secret)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    with session_factory() as session:
        model = session.query(UserModel).filter(UserModel.username == username).first()
        if model is None:
            raise UnauthorizedError('用户不存在或 token 已失效')
        if model.status != 'active':
            raise ForbiddenError('用户已锁定')
        return {
            'id': model.id,
            'username': model.username,
            'email': model.email,
            'nickname': model.nickname,
            'remark': model.remark,
            'status': model.status,
            'isAdmin': bool(model.is_admin),
        }


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get('isAdmin'):
        raise ForbiddenError('仅管理员可执行该操作')
    return current_user


def is_admin_user(current_user: dict | None) -> bool:
    return bool((current_user or {}).get('isAdmin'))


def resolve_visible_owner_user_id(current_user: dict) -> int | None:
    if is_admin_user(current_user):
        return None
    return int(current_user.get('id') or 0)


def ensure_owner_access(current_user: dict, owner_user_id: int | None) -> None:
    if owner_user_id is None:
        if is_admin_user(current_user):
            return
        raise ForbiddenError('无权访问其他用户数据')
    if is_admin_user(current_user):
        return
    if int(current_user.get('id') or 0) != int(owner_user_id):
        raise ForbiddenError('无权访问其他用户数据')


def apply_owner_scope(query, model, current_user: dict):
    owner_user_id = resolve_visible_owner_user_id(current_user)
    if owner_user_id is None:
        return query
    return query.filter(model.owner_user_id == owner_user_id)


def get_primary_admin_user_id(database_url: str) -> int | None:
    session_factory = get_session_factory(database_url)
    with session_factory() as session:
        model = session.query(UserModel).filter(UserModel.is_admin.is_(True)).order_by(UserModel.id.asc()).first()
        if model is None:
            return None
        return int(model.id)
