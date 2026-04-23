from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from ....db import Base
from ....db import CaptchaSessionModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import ValidationError


class CaptchaService:
    def __init__(self, database_url: str, expire_seconds: int):
        self.database_url = database_url
        self.expire_seconds = expire_seconds
        self.engine = get_engine(database_url)
        self.Session = get_session_factory(database_url)
        Base.metadata.create_all(self.engine)

    def create_captcha(self) -> dict:
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=5))
        captcha_key = ''.join(random.choices(string.ascii_letters + string.digits, k=24))
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.expire_seconds)
        with self.Session() as session:
            session.add(
                CaptchaSessionModel(
                    captcha_key=captcha_key,
                    captcha_code=code,
                    expires_at=expires_at.isoformat(),
                    used=False,
                    created_at=now.isoformat(),
                )
            )
            session.commit()
        lines = ''.join(
            f"<line x1='{random.randint(0, 120)}' y1='{random.randint(0, 40)}' x2='{random.randint(0, 120)}' y2='{random.randint(0, 40)}' stroke='rgb({random.randint(120, 200)},{random.randint(120, 200)},{random.randint(120, 200)})' stroke-width='1.2'/>"
            for _ in range(5)
        )
        texts = ''.join(
            f"<text x='{14 + index * 20 + random.randint(-2, 2)}' y='{random.randint(24, 32)}' font-size='24' fill='rgb({random.randint(40, 120)},{random.randint(40, 120)},{random.randint(40, 120)})' transform='rotate({random.randint(-20, 20)} {14 + index * 20} 24)'>{char}</text>"
            for index, char in enumerate(code)
        )
        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='40' viewBox='0 0 120 40'>"
            "<rect width='120' height='40' rx='4' ry='4' fill='#f5f5f5'/>"
            f"{lines}{texts}"
            "</svg>"
        )
        return {
            'captchaKey': captcha_key,
            'captchaSvg': svg,
            'expireSeconds': self.expire_seconds,
        }

    def verify_captcha(self, captcha_key: str, captcha_code: str) -> None:
        with self.Session() as session:
            model = session.get(CaptchaSessionModel, captcha_key)
            if model is None:
                raise ValidationError('验证码不存在或已失效')
            if model.used:
                raise ValidationError('验证码已使用')
            if model.expires_at < datetime.now(timezone.utc).isoformat():
                raise ValidationError('验证码已过期')
            if model.captcha_code.lower() != captcha_code.strip().lower():
                raise ValidationError('验证码错误')
            model.used = True
            session.commit()
