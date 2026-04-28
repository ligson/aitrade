from __future__ import annotations

from ...api_response import page_response
from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import get_current_user
from ....config.config_file import Config
from ....trade.trading_system.trade_store_factory import create_trade_store
from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

router = APIRouter()


class TradeLogPageRequest(BaseModel):
    offset: int = 0
    size: int = 20
    strategy: str | None = None
    side: str | None = None
    result: str | None = None
    symbol: str | None = None
    runId: int | None = None
    createdFrom: str | None = None
    createdTo: str | None = None


@router.post('/page')
def page_trade_logs(
    payload: TradeLogPageRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    store = create_trade_store(config.trade_persistence_config)
    total = store.count_trade_records(
        strategy=payload.strategy,
        side=payload.side,
        result=payload.result,
        symbol=payload.symbol,
        run_id=payload.runId,
        created_from=payload.createdFrom,
        created_to=payload.createdTo,
    )
    rows = store.query_trade_records(
        limit=payload.size,
        offset=payload.offset,
        strategy=payload.strategy,
        side=payload.side,
        result=payload.result,
        symbol=payload.symbol,
        run_id=payload.runId,
        created_from=payload.createdFrom,
        created_to=payload.createdTo,
    )
    return page_response(total, payload.size, payload.offset, rows)


@router.post('/positions')
def current_positions(
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    store = create_trade_store(config.trade_persistence_config)
    return success_response(store.query_position_states())


@router.post('/filter-options')
def trade_log_filter_options(
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    store = create_trade_store(config.trade_persistence_config)
    return success_response({'symbols': store.list_trade_symbols()})
