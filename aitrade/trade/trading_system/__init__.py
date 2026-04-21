from importlib import import_module

__all__ = ['TradingBot', 'MarketDataFetcher', 'RiskManager', 'TradeExecutor', 'TradeStore', 'SQLAlchemyTradeStore']

_MODULE_MAP = {
    'TradingBot': '.trading_bot',
    'MarketDataFetcher': '.market_data_fetcher',
    'RiskManager': '.risk_manager',
    'TradeExecutor': '.trade_executor',
    'TradeStore': '.trade_store',
    'SQLAlchemyTradeStore': '.sqlalchemy_trade_store',
}


def __getattr__(name):
    module_name = _MODULE_MAP.get(name)
    if module_name is None:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    module = import_module(module_name, __name__)
    return getattr(module, name)
