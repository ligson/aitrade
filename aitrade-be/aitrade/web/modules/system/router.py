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


class SystemSettingsEditableRequest(BaseModel):
    gptProvider: str
    gptModel: str
    gptApiKey: str = ''
    gptBaseUrl: str = ''
    persistPosition: bool
    restorePositionOnStartup: bool
    tradeTaskDefaultFeeRate: float = 0
    tradeTaskDefaultSlippageRate: float = 0
    tradeTaskDefaultDailyLossStopEnabled: bool = False
    tradeTaskDefaultDailyLossStopThreshold: float = 100
    supportedSymbols: list[str]
    supportedTimeframes: list[str]
    defaultSymbol: str
    defaultTimeframe: str
    downloadTimerange: str
    dataFormatOhlcv: str
    exportArchiveFormat: str


class SystemSettingsSaveRequest(BaseModel):
    editable: SystemSettingsEditableRequest
    name: str | None = None
    description: str | None = None


class SystemLogFilesRequest(BaseModel):
    offset: int = 0
    size: int = 20
    keyword: str = ''
    type: str = ''


class SystemLogContentRequest(BaseModel):
    filename: str
    tailLines: int = 200


class TradeTaskLogPageRequest(BaseModel):
    offset: int = 0
    size: int = 20
    runnerName: str | None = None
    runId: int | None = None
    eventType: str | None = None
    status: str | None = None
    keyword: str | None = None
    createdFrom: str | None = None
    createdTo: str | None = None


class TradeTaskStartRequest(BaseModel):
    tradeTaskProfileId: int


class TradeTaskProfileSaveRequest(BaseModel):
    id: int | None = None
    name: str
    description: str = ''
    enabled: bool = True
    strategyProfileId: int
    symbol: str
    timeframe: str
    tradeMode: str | None = None
    sandboxTrade: bool | None = None
    tradeLimit: int
    feeRate: float = 0
    slippageRate: float = 0
    dailyLossStopEnabled: bool = False
    dailyLossStopThreshold: float = 100
    runnerName: str = 'default'


class TradeTaskProfileDeleteRequest(BaseModel):
    id: int


@router.post('/settings')
def system_settings(
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = SystemService(config)
    return success_response(service.get_settings())


@router.post('/settings/save')
def system_settings_save(
    payload: SystemSettingsSaveRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(require_admin),
):
    service = SystemService(config)
    return success_response(service.save_settings(payload.model_dump()))


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


@router.post('/trade-task/profiles/list')
def trade_task_profile_list(
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.list_profiles())


@router.post('/trade-task/profiles/save')
def trade_task_profile_save(
    payload: TradeTaskProfileSaveRequest,
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.save_profile(payload.model_dump()))


@router.post('/trade-task/profiles/delete')
def trade_task_profile_delete(
    payload: TradeTaskProfileDeleteRequest,
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.delete_profile(payload.id))


@router.post('/trade-task/status')
def trade_task_status(
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.get_status())


@router.post('/trade-task/logs/page')
def trade_task_log_page(
    payload: TradeTaskLogPageRequest,
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    total, rows = service.page_logs(
        offset=payload.offset,
        size=payload.size,
        runner_name=payload.runnerName,
        run_id=payload.runId,
        event_type=payload.eventType,
        status=payload.status,
        keyword=payload.keyword,
        created_from=payload.createdFrom,
        created_to=payload.createdTo,
    )
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/trade-task/start')
def trade_task_start(
    payload: TradeTaskStartRequest,
    request: Request,
    current_user: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.start(payload.tradeTaskProfileId, current_user))


@router.post('/trade-task/stop')
def trade_task_stop(
    request: Request,
    _: dict = Depends(require_admin),
):
    service: TradeTaskService = request.app.state.trade_task_service
    return success_response(service.stop())
