from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from ...api_response import success_response
from ...dependencies import get_config
from ....config.config_file import Config
from .service import CaptchaService

router = APIRouter()


class CaptchaResponse(BaseModel):
    captchaKey: str
    captchaSvg: str
    expireSeconds: int


@router.post('')
def create_captcha(config: Config = Depends(get_config)):
    service = CaptchaService(
        config.trade_persistence_config['database_url'],
        config.web_captcha_expire_seconds,
    )
    return success_response(service.create_captcha())
