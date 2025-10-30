import logging
import time
from typing import Dict, Any
from ..gpt_signal import SignalGenerator
from .market_data_fetcher import MarketDataFetcher
from .risk_manager import RiskManager
from .trade_executor import TradeExecutor


class TradingBot:
    """主交易机器人控制器"""

    def __init__(self, config):
        """
        初始化交易机器人
        
        Args:
            config: 配置对象
        """
        self.config = config
        
        # 初始化市场数据获取器
        self.market_data_fetcher = MarketDataFetcher(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None
        )
        
        # 初始化交易执行器
        self.trade_executor = TradeExecutor(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None
        )
        
        # 初始化风险管理器
        self.risk_manager = RiskManager()
        
        # 初始化GPT信号生成器
        self.signal_generator = self._init_gpt_signal_generator()
        
        logging.info(
            f"交易所类型: {config.exchange_type}, 代理是否启用: {config.proxy_enable}, 代理地址: {config.proxy_url}"
        )

    def _init_gpt_signal_generator(self) -> SignalGenerator:
        """
        初始化GPT信号生成器
        
        Returns:
            SignalGenerator实例
        """
        # 根据配置选择API提供者
        if self.config.gpt_provider == 'deepseek':
            base_url = "https://api.deepseek.com/v1"
        elif self.config.gpt_provider == 'openai':
            base_url = "https://api.openai.com/v1"
        else:
            # 默认使用DeepSeek
            base_url = "https://api.deepseek.com/v1"
        
        # 初始化信号生成器
        return SignalGenerator(
            api_key=self.config.gpt_api_key,
            base_url=base_url,
            proxy_url=self.config.proxy_url if self.config.proxy_enable else None
        )

    def run(self) -> None:
        """
        运行交易机器人主循环
        """
        logging.info("启动交易机器人...")
        
        while True:
            try:
                # 获取市场数据
                data = self.market_data_fetcher.get_enhanced_market_data(
                    symbol=self.config.trade_symbol,
                    timeframe=str(self.config.trade_timeframe) + 'm',
                    limit=self.config.trade_limit
                )

                # 获取AI信号
                signal = self.signal_generator.get_ai_signal(data)
                logging.debug(f"AI信号: {signal}")

                # 执行交易
                if signal['action'] != 'hold' and signal.get('confidence', 0) > 0.7:
                    self.trade_executor.execute_trade_with_risk_management(
                        self.config.trade_symbol, 
                        signal, 
                        data,
                        self.risk_manager
                    )

                # 监控止损
                position = self.trade_executor.get_position()
                if position and data['price'] <= position['stop_loss']:
                    logging.debug("触发止损!")
                    # 执行止损逻辑

                time.sleep(self.config.trade_timeframe * 60)  # 等待下一个周期

            except Exception as e:
                logging.exception(f"主循环错误: {e}")
                time.sleep(60)