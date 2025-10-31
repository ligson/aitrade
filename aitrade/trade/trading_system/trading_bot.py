import logging
import time

from config import config_file
from .market_data_fetcher import MarketDataFetcher
from .risk_manager import RiskManager
from .trade_executor import TradeExecutor
from ..gpt_signal import SignalGenerator


class TradingBot:
    """主交易机器人控制器

    协调整个交易系统的各个组件，包括市场数据获取、AI信号生成、
    风险管理和交易执行。

    该类是整个交易系统的核心，负责：
    1. 初始化所有子组件
    2. 运行主交易循环
    3. 协调各组件间的数据流
    4. 处理异常和错误

    Attributes:
        config: 配置对象
        market_data_fetcher: 市场数据获取器实例
        trade_executor: 交易执行器实例
        risk_manager: 风险管理器实例
        signal_generator: 信号生成器实例
    """

    def __init__(self, config: config_file.Config):
        """
        初始化交易机器人

        根据配置初始化所有子组件，包括交易所连接、AI服务等。

        Args:
            config: 配置对象，包含所有必要的配置参数

        Example:
            >>> bot = TradingBot(config)
            >>> bot.run()
        """
        self.config = config

        # 初始化市场数据获取器
        logging.info("初始化市场数据获取器")
        self.market_data_fetcher = MarketDataFetcher(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,  # 添加OKX密码参数
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None
        )

        # 初始化交易执行器
        logging.info("初始化交易执行器")
        self.trade_executor = TradeExecutor(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,  # 添加OKX密码参数
            sandbox=config.trade_sandbox_trade,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None
        )

        # 初始化风险管理器
        logging.info("初始化风险管理器")
        self.risk_manager = RiskManager()

        # 初始化GPT信号生成器
        logging.info("初始化GPT信号生成器")
        self.signal_generator = self._init_gpt_signal_generator()

        logging.info(
            f"交易机器人初始化完成 - 交易所类型: {config.exchange_type}, 代理是否启用: {config.proxy_enable}, 代理地址: {config.proxy_url}"
        )

    def _init_gpt_signal_generator(self) -> SignalGenerator:
        """
        初始化GPT信号生成器

        根据配置中的gpt_provider字段选择合适的AI服务提供商。
        支持DeepSeek和OpenAI两种提供商。

        Returns:
            SignalGenerator实例

        Example:
            >>> signal_gen = bot._init_gpt_signal_generator()
        """
        # 根据配置选择API提供者
        if self.config.gpt_provider == 'deepseek':
            base_url = "https://api.deepseek.com/v1"
            logging.info("使用DeepSeek API作为AI服务提供商")
        elif self.config.gpt_provider == 'openai':
            base_url = "https://api.openai.com/v1"
            logging.info("使用OpenAI API作为AI服务提供商")
        else:
            # 默认使用DeepSeek
            base_url = "https://api.deepseek.com/v1"
            logging.warning(f"未知的AI服务提供商: {self.config.gpt_provider}，默认使用DeepSeek")

        # 初始化信号生成器
        signal_generator = SignalGenerator(
            api_key=self.config.gpt_api_key,
            base_url=base_url,
            proxy_url=self.config.proxy_url if self.config.proxy_enable else None
        )

        logging.info("GPT信号生成器初始化完成")
        return signal_generator

    def run(self) -> None:
        """
        运行交易机器人主循环

        这是交易机器人的核心方法，执行以下步骤：
        1. 获取市场数据
        2. 生成交易信号
        3. 风险管理检查
        4. 执行交易
        5. 监控止损
        6. 等待下一个周期

        该循环会一直运行直到程序被手动终止。
        """
        logging.info("启动交易机器人主循环...")

        while True:
            try:
                logging.info("开始新的交易周期")

                # 获取市场数据
                data = self.market_data_fetcher.get_enhanced_market_data(
                    symbol=self.config.trade_symbol,
                    timeframe=str(self.config.trade_timeframe) + 'm',
                    limit=self.config.trade_limit
                )
                logging.debug(f"获取到市场数据: {data['symbol']} 价格: {data['price']}")

                # 获取AI信号
                signal = self.signal_generator.get_ai_signal(data)
                logging.info(f"AI信号生成完成: {signal['action']} (置信度: {signal.get('confidence', 0):.2f})")

                # 执行交易
                # 只有当信号不是'hold'且置信度大于0.7时才考虑交易
                if signal['action'] != 'hold' and signal.get('confidence', 0) > 0.7:
                    logging.info("信号满足交易条件，开始执行交易")
                    self.trade_executor.execute_trade_with_risk_management(
                        self.config.trade_symbol,
                        signal,
                        data,
                        self.risk_manager
                    )
                else:
                    logging.info("当前信号不建议交易")

                # 监控止损
                position = self.trade_executor.get_position()
                if position and data['price'] <= position['stop_loss']:
                    logging.warning(f"触发止损条件! 当前价格: {data['price']}, 止损价格: {position['stop_loss']}")
                    # 执行止损逻辑
                    self._execute_stop_loss(position, data)

                # 等待下一个周期
                sleep_time = self.config.trade_timeframe * 60
                logging.info(f"交易周期完成，等待 {sleep_time} 秒后开始下一周期")
                time.sleep(sleep_time)

            except Exception as e:
                logging.exception(f"主循环发生错误: {e}")
                # 发生错误时等待1分钟后继续
                logging.info("等待60秒后重试...")
                time.sleep(60)

    def _execute_stop_loss(self, position, market_data):
        """
        执行止损操作

        当市场价格触及止损线时，立即执行卖出操作以控制风险。

        Args:
            position: 当前持仓信息，包含入场价、止损价和持仓数量
            market_data: 当前市场数据，包含最新价格等信息
        """
        try:
            logging.info("开始执行止损操作")

            # 创建市价卖出订单
            stop_loss_signal = {
                'action': 'sell',
                'confidence': 1.0,
                'reason': '止损触发',
                'stop_loss_pct': 0.0,  # 止损操作不需要额外的止损设置
                'take_profit_pct': 0.0
            }

            # 使用现有的交易执行方法执行止损
            self.trade_executor.execute_trade_with_risk_management(
                self.config.trade_symbol,
                stop_loss_signal,
                market_data,
                self.risk_manager
            )

            logging.info("止损操作执行完成")

        except Exception as e:
            logging.exception(f"止损执行失败: {e}")
            # 如果止损执行失败，记录错误但不改变持仓状态
            # 这样可以在下一个周期再次尝试执行止损
