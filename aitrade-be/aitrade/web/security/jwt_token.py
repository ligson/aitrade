import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone


def build_token(username: str, secret: str, expire_minutes: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = f'{username}|{int(expires_at.timestamp())}'
    signature = hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f'{payload}|{signature}'.encode('utf-8')).decode('utf-8')


def parse_token(token: str, secret: str) -> str:
    decoded = base64.urlsafe_b64decode(token.encode('utf-8')).decode('utf-8')
    username, expires_at_raw, signature = decoded.split('|', 2)
    payload = f'{username}|{expires_at_raw}'
    expected = hmac.new(secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError('token 签名无效')
    if int(expires_at_raw) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError('token 已过期')
    return username
