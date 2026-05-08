from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from ...api_response import page_response
from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import require_admin
from ....config.config_file import Config
from .service import UserService

router = APIRouter()


class UserPageRequest(BaseModel):
    offset: int = 0
    size: int = 20
    keyword: str = ''


class UserCreateRequest(BaseModel):
    username: str
    email: str
    nickname: str
    password: str
    remark: str = ''
    isAdmin: bool = False


class UserUpdateRequest(BaseModel):
    id: int
    email: str
    nickname: str
    remark: str = ''
    isAdmin: bool = False


class UserResetPasswordRequest(BaseModel):
    id: int
    password: str


class UserChangeStatusRequest(BaseModel):
    id: int
    status: str


@router.post('/page')
def page_users(
    payload: UserPageRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = UserService(config.trade_persistence_config['database_url'])
    service.ensure_init_admin(config.web_init_admin_config)
    total, rows = service.page_users(payload.offset, payload.size, payload.keyword)
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/create')
def create_user(
    payload: UserCreateRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = UserService(config.trade_persistence_config['database_url'])
    return success_response(service.create_user(payload.model_dump()))


@router.post('/update')
def update_user(
    payload: UserUpdateRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = UserService(config.trade_persistence_config['database_url'])
    return success_response(service.update_user(payload.model_dump()))


@router.post('/reset-password')
def reset_password(
    payload: UserResetPasswordRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = UserService(config.trade_persistence_config['database_url'])
    service.reset_password(payload.model_dump())
    return success_response()


@router.post('/change-status')
def change_status(
    payload: UserChangeStatusRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = UserService(config.trade_persistence_config['database_url'])
    service.change_status(payload.model_dump())
    return success_response()
