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
