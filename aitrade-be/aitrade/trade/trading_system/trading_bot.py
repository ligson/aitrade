import logging
import time
from threading import Event

from ...config import config_file

from ..gpt_signal.technical_analyzer import TechnicalAnalyzer
from ..strategies import create_strategy
from .market_data_fetcher import MarketDataFetcher
from .risk_manager import RiskManager
from .trade_executor import TradeExecutor
from .trade_executor import TradingHaltError


class TradingBot:
    """主交易机器人控制器。"""

    def __init__(self, config: config_file.Config, execution_context: dict | None = None):
        self.config = config
        self.execution_context = execution_context or {}

        market_data_sandbox = config.trade_mode == 'sandbox'

        logging.info("初始化市场数据获取器")
        self.market_data_fetcher = MarketDataFetcher(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,
            sandbox=market_data_sandbox,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None,
        )

        logging.info("初始化交易执行器")
        self.trade_executor = TradeExecutor(
            exchange_type=config.exchange_type,
            api_key=config.exchange_api_key,
            secret=config.exchange_api_secret,
            password=config.exchange_password,
            sandbox=market_data_sandbox,
            trade_mode=config.trade_mode,
            proxies={'http': config.proxy_url, 'https': config.proxy_url} if config.proxy_enable else None,
            persistence_config=config.trade_persistence_config,
            paper_balance=config.trade_paper_balance,
            owner_user_id=self.execution_context.get('owner_user_id'),
        )

        logging.info("初始化风险管理器")
        self.risk_manager = RiskManager()

        logging.info("初始化交易策略")
        self.strategy = create_strategy(config)
        self.market_data_requirements = self.strategy.get_market_data_requirements()
        self.required_history = max(config.trade_limit, self.strategy.get_required_history())

        if config.trade_persistence_config.get('restore_position_on_startup'):
            restored = self.trade_executor.restore_position_from_storage(config.trade_symbol)
            if restored:
                logging.info("已恢复本地持仓状态，交易对: %s", config.trade_symbol)
            else:
                logging.info("未恢复到本地持仓状态，交易对: %s", config.trade_symbol)

        logging.info(
            "交易机器人初始化完成 - 交易所类型: %s, trade_mode=%s, 代理是否启用: %s, 代理地址: %s, 策略: %s, K线数量: %s, 数据需求: %s",
            config.exchange_type,
            config.trade_mode,
            config.proxy_enable,
            config.proxy_url,
            config.trade_strategy_type,
            self.required_history,
            self.market_data_requirements,
        )

    def close(self) -> None:
        self.trade_executor.close()

    def get_cycle_interval_seconds(self) -> int:
        timeframe = self.market_data_requirements.get('primary_timeframe') or (str(self.config.trade_timeframe) + 'm')
        return self._timeframe_to_seconds(timeframe)

    def run_cycle(self) -> None:
        logging.info("开始新的交易周期")
        self.trade_executor.check_daily_loss_stop(self.execution_context.get('run_id'))
        data = self._load_market_data()
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
                run_id=self.execution_context.get('run_id'),
                trade_task_profile_id=self.execution_context.get('trade_task_profile_id'),
            )
        else:
            logging.info("当前信号不建议交易")

        position = self.trade_executor.get_position()
        if position and position.get('stop_loss') is not None and data['price'] <= position['stop_loss']:
            logging.warning("触发止损条件! 当前价格: %s, 止损价格: %s", data['price'], position['stop_loss'])
            self._execute_stop_loss(position, data)

    def _load_market_data(self) -> dict:
        primary_timeframe = self.market_data_requirements.get('primary_timeframe') or (str(self.config.trade_timeframe) + 'm')
        primary_data = self.market_data_fetcher.get_enhanced_market_data(
            symbol=self.config.trade_symbol,
            timeframe=primary_timeframe,
            limit=self.required_history,
        )
        context_timeframes = list(self.market_data_requirements.get('context_timeframes') or [])
        extra_feeds = list(self.market_data_requirements.get('extra_feeds') or [])
        if not context_timeframes and not extra_feeds:
            return primary_data

        contexts = {}
        context_history_getter = getattr(self.strategy, 'get_required_context_history', None)
        context_histories = context_history_getter() if callable(context_history_getter) else {}
        decision_ts = primary_data['timestamps'][-1]
        for timeframe in context_timeframes:
            context_limit = max(int(context_histories.get(timeframe, self.required_history)), 10)
            context_data = self.market_data_fetcher.get_enhanced_market_data(
                symbol=self.config.trade_symbol,
                timeframe=timeframe,
                limit=context_limit,
            )
            contexts[timeframe] = self._trim_context_market_data(context_data, decision_ts)

        feeds = self._load_extra_feeds(extra_feeds, primary_data)
        merged_data = dict(primary_data)
        merged_data['primary'] = primary_data
        merged_data['contexts'] = contexts
        merged_data['feeds'] = feeds
        merged_data['decisionTimestamp'] = decision_ts
        return merged_data

    def _load_extra_feeds(self, feed_requirements: list[dict], primary_data: dict) -> dict:
        feeds = {}
        for requirement in feed_requirements:
            feed_type = str(requirement.get('type') or '').strip()
            if not feed_type:
                continue
            try:
                if feed_type == 'trade_flow':
                    feeds[feed_type] = self._build_trade_flow_feed(requirement)
                    continue
                if feed_type == 'indicator':
                    feeds[feed_type] = self._build_indicator_feed(requirement, primary_data)
                    continue
                logging.warning('检测到未支持的扩展 feed 类型: %s', feed_type)
                feeds[feed_type] = {
                    'feedType': feed_type,
                    'available': False,
                    'required': bool(requirement.get('required')),
                    'reason': f'暂不支持的 feed 类型: {feed_type}',
                    'payload': {},
                    'meta': dict(requirement.get('params') or {}),
                }
            except Exception as exc:
                logging.error('加载扩展 feed 失败: feed_type=%s error=%s', feed_type, exc)
                feeds[feed_type] = {
                    'feedType': feed_type,
                    'available': False,
                    'required': bool(requirement.get('required')),
                    'reason': f'feed 加载失败: {exc}',
                    'payload': {},
                    'meta': dict(requirement.get('params') or {}),
                }
        return feeds

    def _build_trade_flow_feed(self, requirement: dict) -> dict:
        params = dict(requirement.get('params') or {})
        lookback_trades = max(int(params.get('lookback_trades', 200) or 200), 20)
        freshness_seconds = int(requirement.get('freshness_seconds') or 0)
        raw_trades = self.market_data_fetcher.fetch_recent_trades(self.config.trade_symbol, limit=lookback_trades)
        trades = [item for item in raw_trades if isinstance(item, dict)]
        if not trades:
            return {
                'feedType': 'trade_flow',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': '未获取到近期成交数据',
                'payload': {},
                'meta': {
                    'lookbackTrades': lookback_trades,
                    'freshnessSeconds': freshness_seconds,
                },
            }

        buy_count = 0
        sell_count = 0
        buy_notional = 0.0
        sell_notional = 0.0
        latest_timestamp = None
        latest_price = None
        for item in trades:
            amount = self._to_float(item.get('amount')) or 0.0
            price = self._to_float(item.get('price')) or 0.0
            side = str(item.get('side') or '').lower()
            timestamp = item.get('timestamp')
            if isinstance(timestamp, (int, float)):
                latest_timestamp = max(int(timestamp), latest_timestamp or int(timestamp))
            if price > 0:
                latest_price = price
            notional = amount * price
            if side == 'buy':
                buy_count += 1
                buy_notional += notional
            elif side == 'sell':
                sell_count += 1
                sell_notional += notional

        total_count = buy_count + sell_count
        total_notional = buy_notional + sell_notional
        if total_count <= 0 or total_notional <= 0:
            return {
                'feedType': 'trade_flow',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': '近期成交缺少可用方向或金额信息',
                'payload': {},
                'meta': {
                    'lookbackTrades': lookback_trades,
                    'latestTimestamp': latest_timestamp,
                    'freshnessSeconds': freshness_seconds,
                },
            }

        now_ms = int(time.time() * 1000)
        if latest_timestamp is None:
            return {
                'feedType': 'trade_flow',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': '近期成交缺少有效时间戳',
                'payload': {},
                'meta': {
                    'lookbackTrades': lookback_trades,
                    'tradeCount': total_count,
                    'freshnessSeconds': freshness_seconds,
                },
            }
        age_seconds = max((now_ms - latest_timestamp) / 1000, 0.0)
        if freshness_seconds > 0 and age_seconds > freshness_seconds:
            return {
                'feedType': 'trade_flow',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': f'trade_flow 数据已过期，最新成交距今 {age_seconds:.1f} 秒',
                'asOf': self._timestamp_ms_to_iso(latest_timestamp),
                'payload': {},
                'meta': {
                    'lookbackTrades': lookback_trades,
                    'tradeCount': total_count,
                    'latestTimestamp': latest_timestamp,
                    'freshnessSeconds': freshness_seconds,
                    'ageSeconds': age_seconds,
                },
            }

        as_of = self._timestamp_ms_to_iso(latest_timestamp) if latest_timestamp is not None else None
        payload = {
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_ratio': buy_count / total_count,
            'buy_notional': buy_notional,
            'sell_notional': sell_notional,
            'notional_imbalance': (buy_notional - sell_notional) / total_notional,
            'latest_price': latest_price,
            'latest_timestamp': latest_timestamp,
        }
        return {
            'feedType': 'trade_flow',
            'available': True,
            'required': bool(requirement.get('required')),
            'reason': '近期成交数据加载成功',
            'asOf': as_of,
            'freshnessSeconds': freshness_seconds,
            'payload': payload,
            'meta': {
                'lookbackTrades': lookback_trades,
                'tradeCount': total_count,
            },
        }

    def _build_indicator_feed(self, requirement: dict, primary_data: dict) -> dict:
        params = dict(requirement.get('params') or {})
        indicator_key = str(params.get('indicator_key') or '').strip().lower()
        lookback_candles = max(int(params.get('lookback_candles', 100) or 100), 30)
        period = max(int(params.get('period', 14) or 14), 2)
        lower_threshold = float(params.get('lower_threshold', 30.0) or 30.0)
        upper_threshold = float(params.get('upper_threshold', 70.0) or 70.0)
        confirm_crossover = bool(params.get('confirm_crossover', True))
        closes = list(primary_data.get('closes') or [])
        timestamps = list(primary_data.get('timestamps') or [])
        price = self._to_float(primary_data.get('price')) or 0.0
        if indicator_key not in {'rsi', 'macd'}:
            return {
                'feedType': 'indicator',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': f'暂不支持的 indicator_key: {indicator_key or "空值"}',
                'payload': {},
                'meta': params,
            }
        if len(closes) < lookback_candles:
            return {
                'feedType': 'indicator',
                'available': False,
                'required': bool(requirement.get('required')),
                'reason': f'indicator 所需K线不足，至少需要 {lookback_candles} 根',
                'payload': {},
                'meta': {
                    **params,
                    'currentHistory': len(closes),
                },
            }
        latest_timestamp = int(timestamps[-1]) if timestamps else None
        closes_window = closes[-lookback_candles:]
        as_of = self._timestamp_ms_to_iso(latest_timestamp)
        if indicator_key == 'rsi':
            if len(closes_window) < period + 1:
                return {
                    'feedType': 'indicator',
                    'available': False,
                    'required': bool(requirement.get('required')),
                    'reason': f'RSI 所需K线不足，至少需要 {period + 1} 根',
                    'payload': {},
                    'meta': {
                        **params,
                        'currentHistory': len(closes_window),
                    },
                }
            rsi_values = TechnicalAnalyzer.compute_rsi(closes_window, period=period)
            rsi_value = float(rsi_values[-1])
            rsi_analysis = TechnicalAnalyzer.analyze_rsi(rsi_value)
            bias = 'hold'
            score = 0.0
            reason = str(rsi_analysis.get('details') or 'RSI 未形成明显倾向')
            if rsi_value <= lower_threshold:
                bias = 'buy'
                score = float(rsi_analysis.get('strength') or 0.0)
                reason = f'RSI {rsi_value:.1f} 跌入低阈值区域'
            elif rsi_value >= upper_threshold:
                bias = 'sell'
                score = float(rsi_analysis.get('strength') or 0.0)
                reason = f'RSI {rsi_value:.1f} 升至高阈值区域'
            return {
                'feedType': 'indicator',
                'available': True,
                'required': bool(requirement.get('required')),
                'reason': 'RSI 指标计算成功',
                'asOf': as_of,
                'payload': {
                    'indicator_key': 'rsi',
                    'timeframe': str(params.get('primary_timeframe') or ''),
                    'bias': bias,
                    'score': score,
                    'confidence': score,
                    'reason': reason,
                    'values': {
                        'rsi': rsi_value,
                        'lower_threshold': lower_threshold,
                        'upper_threshold': upper_threshold,
                    },
                    'latest_price': price,
                    'latest_timestamp': latest_timestamp,
                },
                'meta': {
                    **params,
                    'condition': rsi_analysis.get('condition'),
                },
            }

        macd_analysis, macd_line, signal_line, macd_histogram = TechnicalAnalyzer.analyze_macd(closes_window)
        bias = 'hold'
        score = 0.0
        reason = str(macd_analysis.get('details') or 'MACD 未形成明显倾向')
        crossover = str(macd_analysis.get('crossover') or 'none')
        trend = str(macd_analysis.get('trend') or 'neutral')
        momentum = float(macd_analysis.get('momentum') or 0.0)
        if confirm_crossover:
            if crossover == 'golden':
                bias = 'buy'
                score = momentum
            elif crossover == 'death':
                bias = 'sell'
                score = momentum
        else:
            if trend == 'bullish' and float(macd_histogram) > 0:
                bias = 'buy'
                score = momentum
            elif trend == 'bearish' and float(macd_histogram) < 0:
                bias = 'sell'
                score = momentum
        return {
            'feedType': 'indicator',
            'available': True,
            'required': bool(requirement.get('required')),
            'reason': 'MACD 指标计算成功',
            'asOf': as_of,
            'payload': {
                'indicator_key': 'macd',
                'timeframe': str(params.get('primary_timeframe') or ''),
                'bias': bias,
                'score': score,
                'confidence': score,
                'reason': reason,
                'values': {
                    'macd_line': float(macd_line),
                    'macd_signal': float(signal_line),
                    'macd_histogram': float(macd_histogram),
                    'trend': trend,
                    'crossover': crossover,
                },
                'latest_price': price,
                'latest_timestamp': latest_timestamp,
            },
            'meta': {
                **params,
                'trend': trend,
                'crossover': crossover,
            },
        }

    @staticmethod
    def _trim_context_market_data(context_data: dict, decision_ts: int) -> dict:
        valid_indexes = [index for index, timestamp in enumerate(context_data.get('timestamps', [])) if timestamp <= decision_ts]
        if not valid_indexes:
            return {
                'symbol': context_data.get('symbol'),
                'timestamp': context_data.get('timestamp'),
                'price': context_data.get('price'),
                'timestamps': [],
                'opens': [],
                'highs': [],
                'lows': [],
                'closes': [],
                'volumes': [],
                'ohlcv': [],
                'technicals': {},
            }
        last_index = valid_indexes[-1] + 1
        closes = context_data.get('closes', [])[:last_index]
        trimmed = {
            'symbol': context_data.get('symbol'),
            'timestamp': context_data.get('timestamp'),
            'price': closes[-1] if closes else context_data.get('price'),
            'timestamps': context_data.get('timestamps', [])[:last_index],
            'opens': context_data.get('opens', [])[:last_index],
            'highs': context_data.get('highs', [])[:last_index],
            'lows': context_data.get('lows', [])[:last_index],
            'closes': closes,
            'volumes': context_data.get('volumes', [])[:last_index],
            'ohlcv': context_data.get('ohlcv', [])[:last_index],
        }
        trimmed['technicals'] = {}
        return trimmed

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

    @staticmethod
    def _timestamp_ms_to_iso(timestamp_ms: int | None) -> str | None:
        if timestamp_ms is None:
            return None
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp_ms / 1000))

    @staticmethod
    def _timeframe_to_seconds(timeframe: str) -> int:
        normalized = str(timeframe or '').strip().lower()
        if normalized.endswith('m') and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 60
        if normalized.endswith('h') and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 3600
        if normalized.endswith('d') and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 86400
        raise ValueError(f'不支持的周期格式: {timeframe}')

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
            except TradingHaltError:
                raise
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
                run_id=self.execution_context.get('run_id'),
                trade_task_profile_id=self.execution_context.get('trade_task_profile_id'),
            )
            logging.info("止损操作执行完成")
        except TradingHaltError:
            raise
        except Exception as e:
            logging.exception("止损执行失败: %s", e)
