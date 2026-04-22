from __future__ import annotations

from datetime import datetime, timezone

from ....db import Base
from ....db import UserModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import ForbiddenError
from ...exceptions import UnauthorizedError
from ...exceptions import ValidationError
from ...security import build_token
from ...security import hash_password
from ...security import verify_password
from ..captcha.service import CaptchaService


class AuthService:
    def __init__(self, database_url: str, captcha_expire_seconds: int, init_admin_config: dict | None = None):
        self.database_url = database_url
        self.engine = get_engine(database_url)
        self.Session = get_session_factory(database_url)
        self.captcha_service = CaptchaService(database_url, captcha_expire_seconds)
        Base.metadata.create_all(self.engine)
        self.init_admin_config = init_admin_config or {}

    def ensure_init_admin(self) -> None:
        if not self.init_admin_config.get('enabled', True):
            return
        with self.Session() as session:
            existing = session.query(UserModel).filter(UserModel.username == self.init_admin_config['username']).first()
            if existing is not None:
                return
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                UserModel(
                    username=self.init_admin_config['username'],
                    email=self.init_admin_config['email'],
                    nickname=self.init_admin_config['nickname'],
                    remark=self.init_admin_config.get('remark', ''),
                    password_hash=hash_password(self.init_admin_config['password']),
                    status='active',
                    is_admin=True,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

    def login(self, payload: dict, jwt_secret: str, jwt_expire_minutes: int) -> dict:
        self.ensure_init_admin()
        username = payload.get('username', '').strip()
        password = payload.get('password', '').strip()
        captcha_key = payload.get('captchaKey', '').strip()
        captcha_code = payload.get('captchaCode', '').strip()
        if not username or not password or not captcha_key or not captcha_code:
            raise ValidationError('登录参数不完整')
        self.captcha_service.verify_captcha(captcha_key, captcha_code)
        with self.Session() as session:
            model = session.query(UserModel).filter(UserModel.username == username).first()
            if model is None or not verify_password(password, model.password_hash):
                raise UnauthorizedError('用户名或密码错误')
            if model.status == 'locked':
                raise ForbiddenError('用户已锁定')
            model.last_login_at = datetime.now(timezone.utc).isoformat()
            session.commit()
            token = build_token(model.username, jwt_secret, jwt_expire_minutes)
            return {
                'token': token,
                'user': {
                    'id': model.id,
                    'username': model.username,
                    'email': model.email,
                    'nickname': model.nickname,
                    'remark': model.remark,
                    'status': model.status,
                    'isAdmin': bool(model.is_admin),
                },
            }
