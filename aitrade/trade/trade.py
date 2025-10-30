import logging

from .trading_system import TradingBot
from ..config import config_file


class OptimizedCryptoBot:
    def __init__(self, cfg: config_file.Config):
        self.trading_bot = TradingBot(cfg)
        logging.info("优化版交易机器人已初始化")

    def run(self):
        """运行交易机器人"""
        self.trading_bot.run()
