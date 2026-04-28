import logging
from threading import Event

from .trading_system.trading_bot import TradingBot
from ..config import config_file


class OptimizedCryptoBot:
    def __init__(self, cfg: config_file.Config, execution_context: dict | None = None):
        self.trading_bot = TradingBot(cfg, execution_context=execution_context)
        logging.info("优化版交易机器人已初始化")

    def run(self, stop_event: Event | None = None):
        """运行交易机器人"""
        self.trading_bot.run(stop_event=stop_event)

    def close(self):
        self.trading_bot.close()
