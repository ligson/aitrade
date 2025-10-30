"""交易系统模块

该模块包含了完整的交易系统实现，主要由以下组件构成：
- TradingBot: 主交易机器人控制器，协调各个组件
- MarketDataFetcher: 市场数据获取器，负责从交易所获取市场数据
- RiskManager: 风险管理器，负责交易风险控制
- TradeExecutor: 交易执行器，负责实际执行交易订单

这些组件协同工作，形成一个完整的自动化交易系统。
"""

from .trading_bot import TradingBot
from .market_data_fetcher import MarketDataFetcher
from .risk_manager import RiskManager
from .trade_executor import TradeExecutor

__all__ = ['TradingBot', 'MarketDataFetcher', 'RiskManager', 'TradeExecutor']