from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from pydantic import BaseModel

from ...api_response import page_response
from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import require_admin
from ....config.config_file import Config
from .service import SystemService
from .trade_task_service import TradeTaskService

router = APIRouter()


class SystemLogFilesRequest(BaseModel):
    offset: int = 0
    size: int = 20
    keyword: str = ''
    type: str = ''


class SystemLogContentRequest(BaseModel):
    filename: str
    tailLines: int = 200


@router.post('/settings')
def system_settings(
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = SystemService(config)
    return success_response(service.get_settings())


@router.post('/logs/files')
def system_log_files(
    payload: SystemLogFilesRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = SystemService(config)
    total, rows = service.list_log_files(payload.offset, payload.size, payload.keyword, payload.type)
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/logs/content')
def system_log_content(
    payload: SystemLogContentRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = SystemService(config)
    return success_response(service.read_log_content(payload.filename, payload.tailLines))


@router.post('/trade-task/status')
def trade_task_status(
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.get_status())


@router.post('/trade-task/start')
def trade_task_start(
    request: Request,
    current_user: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.start(current_user))


@router.post('/trade-task/stop')
def trade_task_stop(
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.stop())
