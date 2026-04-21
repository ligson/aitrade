from typing import Any, Dict

from sqlalchemy.engine import make_url

from .sqlalchemy_trade_store import SQLAlchemyTradeStore
from .trade_store import TradeStore


def create_trade_store(persistence_config: Dict[str, Any]) -> TradeStore:
    database_url = persistence_config['database_url']
    return SQLAlchemyTradeStore(database_url)


def summarize_database_target(database_url: str) -> str:
    url = make_url(database_url)
    backend = url.get_backend_name()
    if backend == 'sqlite':
        return f'{backend}:{url.database or ":memory:"}'
    host = url.host or 'localhost'
    database = url.database or ''
    return f'{backend}://{host}/{database}'
