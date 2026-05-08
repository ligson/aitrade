from __future__ import annotations

from datetime import datetime, timezone

from ....db import Base
from ....db import UserModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import ForbiddenError
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ...security import hash_password


class UserService:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = get_engine(database_url)
        self.Session = get_session_factory(database_url)
        Base.metadata.create_all(self.engine)

    def ensure_init_admin(self, init_admin_config: dict) -> None:
        if not init_admin_config.get('enabled', True):
            return
        with self.Session() as session:
            existing = session.query(UserModel).filter(UserModel.username == init_admin_config['username']).first()
            if existing is not None:
                return
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                UserModel(
                    username=init_admin_config['username'],
                    email=init_admin_config['email'],
                    nickname=init_admin_config['nickname'],
                    remark=init_admin_config.get('remark', ''),
                    password_hash=hash_password(init_admin_config['password']),
                    status='active',
                    is_admin=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    def page_users(self, offset: int, size: int, keyword: str = '') -> tuple[int, list[dict]]:
        with self.Session() as session:
            query = session.query(UserModel)
            if keyword:
                like_value = f'%{keyword}%'
                query = query.filter(
                    (UserModel.username.like(like_value)) |
                    (UserModel.email.like(like_value)) |
                    (UserModel.nickname.like(like_value))
                )
            total = query.count()
            models = query.order_by(UserModel.id.desc()).offset(offset).limit(size).all()
            return total, [self._to_dict(model) for model in models]

    def create_user(self, payload: dict) -> dict:
        username = payload['username'].strip()
        email = payload['email'].strip()
        nickname = payload['nickname'].strip()
        password = payload['password'].strip()
        remark = payload.get('remark', '').strip()
        if not username or not email or not nickname or not password:
            raise ValidationError('用户名、邮箱、昵称、密码不能为空')
        with self.Session() as session:
            if session.query(UserModel).filter(UserModel.username == username).first() is not None:
                raise ValidationError('用户名已存在')
            if session.query(UserModel).filter(UserModel.email == email).first() is not None:
                raise ValidationError('邮箱已存在')
            now = datetime.now(timezone.utc).isoformat()
            model = UserModel(
                username=username,
                email=email,
                nickname=nickname,
                remark=remark,
                password_hash=hash_password(password),
                status='active',
                is_admin=bool(payload.get('isAdmin', False)),
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
            return self._to_dict(model)

    def update_user(self, payload: dict) -> dict:
        user_id = int(payload['id'])
        with self.Session() as session:
            model = session.get(UserModel, user_id)
            if model is None:
                raise NotFoundError('用户不存在')
            model.email = payload['email'].strip()
            model.nickname = payload['nickname'].strip()
            model.remark = payload.get('remark', '').strip()
            model.is_admin = bool(payload.get('isAdmin', False))
            model.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()
            session.refresh(model)
            return self._to_dict(model)

    def reset_password(self, payload: dict) -> None:
        user_id = int(payload['id'])
        password = payload['password'].strip()
        if not password:
            raise ValidationError('新密码不能为空')
        with self.Session() as session:
            model = session.get(UserModel, user_id)
            if model is None:
                raise NotFoundError('用户不存在')
            model.password_hash = hash_password(password)
            model.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()

    def change_status(self, payload: dict) -> None:
        user_id = int(payload['id'])
        status = payload['status']
        if status not in {'active', 'locked'}:
            raise ValidationError('状态只支持 active 或 locked')
        with self.Session() as session:
            model = session.get(UserModel, user_id)
            if model is None:
                raise NotFoundError('用户不存在')
            model.status = status
            model.updated_at = datetime.now(timezone.utc).isoformat()
            session.commit()

    @staticmethod
    def _to_dict(model: UserModel) -> dict:
        return {
            'id': model.id,
            'username': model.username,
            'email': model.email,
            'nickname': model.nickname,
            'remark': model.remark,
            'status': model.status,
            'isAdmin': bool(model.is_admin),
            'createdAt': model.created_at,
            'updatedAt': model.updated_at,
            'lastLoginAt': model.last_login_at,
        }
