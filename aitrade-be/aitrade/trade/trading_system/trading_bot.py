import logging
import time
from threading import Event

from ...config import config_file

from ..strategies import create_strategy
from .market_data_fetcher import MarketDataFetcher
from .risk_manager import RiskManager
from .trade_executor import TradeExecutor


class TradingBot:
    """主交易机器人控制器。"""

    def __init__(self, config: config_file.Config):
        self.config = config

        logging.info("初始化市场数据获取器")
        self.market_data_fetcher = MarketDataFetcher(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None,
        )

        logging.info("初始化交易执行器")
        self.trade_executor = TradeExecutor(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None,
            persistence_config=config.trade_persistence_config,
        )

        logging.info("初始化风险管理器")
        self.risk_manager = RiskManager()

        logging.info("初始化交易策略")
        self.strategy = create_strategy(config)
        self.required_history = max(config.trade_limit, self.strategy.get_required_history())

        if config.trade_persistence_config.get('restore_position_on_startup'):
            restored = self.trade_executor.restore_position_from_storage(config.trade_symbol)
            if restored:
                logging.info("已恢复本地持仓状态，交易对: %s", config.trade_symbol)
            else:
                logging.info("未恢复到本地持仓状态，交易对: %s", config.trade_symbol)

        logging.info(
            "交易机器人初始化完成 - 交易所类型: %s, 代理是否启用: %s, 代理地址: %s, 策略: %s, K线数量: %s",
            config.exchange_type,
            config.proxy_enable,
            config.proxy_url,
            config.trade_strategy_type,
            self.required_history,
        )

    def close(self) -> None:
        self.trade_executor.close()

    def get_cycle_interval_seconds(self) -> int:
        return self.config.trade_timeframe * 60

    def run_cycle(self) -> None:
        logging.info("开始新的交易周期")
        data = self.market_data_fetcher.get_enhanced_market_data(
            symbol=self.config.trade_symbol,
            timeframe=str(self.config.trade_timeframe) + 'm',
            limit=self.required_history,
        )
        logging.debug("获取到市场数据: %s 价格: %s", data['symbol'], data['price'])

        position = self.trade_executor.get_position()
        signal = self.strategy.generate_signal(data, position)
        logging.info("策略信号生成完成: %s (%s)", signal['action'], signal.get('reason', '无原因'))

        if position:
            self.trade_executor.update_position_risk(
                symbol=self.config.trade_symbol,
                stop_loss=signal.get('stop_loss_price'),
                trailing_stop_price=signal.get('trailing_stop_price'),
                market_price=data['price'],
                meta=signal.get('meta'),
            )
            position = self.trade_executor.get_position()

        if signal['action'] != 'hold':
            logging.info("信号满足交易条件，开始执行交易")
            self.trade_executor.execute_trade_with_risk_management(
                self.config.trade_symbol,
                signal,
                data,
                self.risk_manager,
                trigger_source='strategy_signal',
            )
        else:
            logging.info("当前信号不建议交易")

        position = self.trade_executor.get_position()
        if position and position.get('stop_loss') is not None and data['price'] <= position['stop_loss']:
            logging.warning("触发止损条件! 当前价格: %s, 止损价格: %s", data['price'], position['stop_loss'])
            self._execute_stop_loss(position, data)

    def run(self, stop_event: Event | None = None) -> None:
        logging.info("启动交易机器人主循环...")
        effective_stop_event = stop_event or Event()

        while not effective_stop_event.is_set():
            try:
                self.run_cycle()
                sleep_time = self.get_cycle_interval_seconds()
                logging.info("交易周期完成，等待 %s 秒后开始下一周期", sleep_time)
                if effective_stop_event.wait(sleep_time):
                    logging.info("收到停止信号，交易机器人准备退出")
                    break
            except Exception as e:
                logging.exception("主循环发生错误: %s", e)
                logging.info("等待60秒后重试...")
                if effective_stop_event.wait(60):
                    logging.info("收到停止信号，交易机器人准备退出")
                    break

    def _execute_stop_loss(self, position, market_data):
        try:
            logging.info("开始执行止损操作")
            if position is None:
                logging.warning("无有效持仓，跳过止损执行")
                return

            stop_loss_signal = {
                'action': 'sell',
                'confidence': 1.0,
                'reason': '止损触发',
                'strategy': position.get('strategy', self.config.trade_strategy_type),
                'force_execution': True,
                'stop_loss_pct': 0.0,
                'take_profit_pct': 0.0,
                'meta': position.get('meta', {}),
            }

            self.trade_executor.execute_trade_with_risk_management(
                self.config.trade_symbol,
                stop_loss_signal,
                market_data,
                self.risk_manager,
                trigger_source='stop_loss_trigger',
            )
            logging.info("止损操作执行完成")
        except Exception as e:
            logging.exception("止损执行失败: %s", e)
