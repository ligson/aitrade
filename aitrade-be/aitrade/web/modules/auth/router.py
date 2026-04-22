from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import get_current_user
from ....config.config_file import Config
from ..captcha.router import create_captcha as create_captcha_impl
from .service import AuthService

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str
    captchaKey: str
    captchaCode: str


@router.post('/captcha')
def create_captcha(config: Config = Depends(get_config)):
    return create_captcha_impl(config)


@router.post('/login')
def login(payload: LoginRequest, config: Config = Depends(get_config)):
    service = AuthService(
        config.trade_persistence_config['database_url'],
        config.web_captcha_expire_seconds,
        config.web_init_admin_config,
    )
    return success_response(service.login(payload.model_dump(), config.web_jwt_secret, config.web_jwt_expire_minutes))


@router.get('/me')
def current_user_get(current_user: dict = Depends(get_current_user)):
    return success_response(current_user)


@router.post('/me')
def current_user_post(current_user: dict = Depends(get_current_user)):
    return success_response(current_user)


@router.post('/logout')
def logout():
    return success_response({'loggedOut': True})
