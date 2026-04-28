from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from ...api_response import page_response
from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import get_current_user
from ....config.config_file import Config
from .service import BacktestService

router = APIRouter()


class BacktestDataRequest(BaseModel):
    symbol: str | None = None
    timeframe: str | None = None
    timerange: str | None = None


class BacktestDataCatalogRequest(BaseModel):
    symbol: str = ''
    timeframe: str = ''
    keyword: str = ''
    offset: int = 0
    size: int = 20


class BacktestDataExportRequest(BaseModel):
    files: list[str] = []


class BacktestDataDeleteRequest(BaseModel):
    filename: str


class BacktestRunRequest(BaseModel):
    strategyProfileId: int
    dataFile: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    timerange: str | None = None
    initialBalance: float = 10000
    feeRate: float = 0.001
    slippageRate: float = 0


class BacktestStopRequest(BaseModel):
    id: int


class BacktestPageRequest(BaseModel):
    offset: int = 0
    size: int = 20
    keyword: str = ''
    status: str = ''


class BacktestDetailRequest(BaseModel):
    id: int


class BacktestTradesPageRequest(BaseModel):
    jobId: int
    offset: int = 0
    size: int = 50


@router.post('/data/options')
def backtest_data_options(
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.get_data_options())


@router.post('/data/status')
def backtest_data_status(
    payload: BacktestDataRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.get_data_status(payload.model_dump()))


@router.post('/data/catalog')
def backtest_data_catalog(
    payload: BacktestDataCatalogRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    total, rows = service.page_data_catalog(payload.symbol, payload.timeframe, payload.keyword, payload.offset, payload.size)
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/data/download')
def backtest_download_data(
    payload: BacktestDataRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.download_data(payload.model_dump()))


@router.post('/data/export')
def backtest_export_data(
    payload: BacktestDataExportRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    archive_name, archive_bytes = service.export_data_archive(payload.files)
    return Response(
        content=archive_bytes,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{archive_name}"'},
    )


@router.post('/data/import')
async def backtest_import_data(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(await service.import_data_archive(file, overwrite=overwrite))


@router.post('/data/delete')
def backtest_delete_data(
    payload: BacktestDataDeleteRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.delete_data_file(payload.filename))


@router.post('/run')
def run_backtest(
    payload: BacktestRunRequest,
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.create_job(payload.model_dump(), current_user=current_user))


@router.post('/stop')
def stop_backtest(
    payload: BacktestStopRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.stop_job(payload.id))


@router.post('/page')
def page_backtests(
    payload: BacktestPageRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    total, rows = service.page_jobs(payload.offset, payload.size, payload.keyword, payload.status)
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/detail')
def backtest_detail(
    payload: BacktestDetailRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    return success_response(service.get_job_detail(payload.id))


@router.post('/trades')
def backtest_trades(
    payload: BacktestTradesPageRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    service = BacktestService(config)
    total, rows = service.page_job_trades(payload.jobId, payload.offset, payload.size)
    return page_response(total, payload.size, payload.offset, rows)
