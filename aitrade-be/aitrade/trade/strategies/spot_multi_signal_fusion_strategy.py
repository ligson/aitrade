from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from ...config.config_file import DEFAULT_BTC_SPOT_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG
from .base_strategy import BaseStrategy


class SpotMultiSignalFusionStrategy(BaseStrategy):
    name = 'spot_multi_signal_fusion'

    def __init__(self, runtime_config):
        super().__init__(runtime_config.trade_strategy_spot_multi_signal_fusion_config)
        self.market_feeds_config = dict(runtime_config.trade_market_feeds_config or {})

    def get_market_data_requirements(self) -> Dict[str, Any]:
        context_timeframes = []
        extra_feeds = []
        trade_flow_config = dict(self.market_feeds_config.get('trade_flow') or {})
        if self._is_kline_trend_breakout_node_enabled():
            context_timeframes.append('4h')
        if self._is_trade_flow_enabled(trade_flow_config):
            extra_feeds.append({
                'type': 'trade_flow',
                'required': not bool(self.config.get('allow_degraded', True)),
                'freshness_seconds': int(trade_flow_config.get('freshness_seconds', 120) or 120),
                'params': {
                    'lookback_trades': int(trade_flow_config.get('lookback_trades', 200) or 200),
                },
            })
        return {
            'primary_timeframe': None,
            'context_timeframes': context_timeframes,
            'extra_feeds': extra_feeds,
        }

    def get_required_history(self) -> int:
        histories = [int(self.config.get('shared_atr_period', 14)) + 2, 35]
        if bool(self.config.get('enable_technical_node', True)):
            histories.append(max(
                int(self.config.get('technical_ema_period', 55)) + 2,
                int(self.config.get('technical_breakout_lookback', 20)) + 2,
            ))
        if bool(self.config.get('enable_kline_breakout_node', False)):
            histories.append(max(
                int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['donchian_entry']) + 2,
                int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['donchian_exit']) + 2,
                int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['ema_period']) + int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['ema_slope_lookback']) + 2,
                int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['volume_ma_period']) + 2,
            ))
        if self._is_kline_trend_breakout_node_enabled():
            histories.append(max(
                int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['breakout_lookback']) + 2,
                int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['volume_ma_period']) + 2,
            ))
        return max(histories)

    def get_required_context_history(self) -> Dict[str, int]:
        if not self._is_kline_trend_breakout_node_enabled():
            return {}
        ema_slow_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['ema_slow_period'])
        adx_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['adx_period'])
        return {
            '4h': max(ema_slow_period + 2, adx_period * 2 + 2),
        }

    def generate_signal(self, market_data: Dict[str, Any], position: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        primary_data = market_data.get('primary') or market_data
        closes = primary_data.get('closes', [])
        highs = primary_data.get('highs', [])
        lows = primary_data.get('lows', [])
        volumes = primary_data.get('volumes', [])
        required_history = self.get_required_history()
        if len(closes) < required_history:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'融合策略所需K线不足，至少需要 {required_history} 根',
                'strategy': self.name,
                'asof': market_data.get('decisionTimestamp') or market_data.get('timestamp'),
                'signal_sources': [],
                'signal_score': 0.0,
                'degraded': True,
                'meta': {
                    'required_history': required_history,
                    'current_history': len(closes),
                },
            }

        close_series = pd.Series(closes, dtype='float64')
        high_series = pd.Series(highs, dtype='float64')
        low_series = pd.Series(lows, dtype='float64')
        volume_series = pd.Series(volumes, dtype='float64')
        current_price = float(close_series.iloc[-1])

        node_results: list[dict[str, Any]] = []
        enabled_nodes = 0
        available_nodes = 0

        if bool(self.config.get('enable_technical_node', True)):
            enabled_nodes += 1
            technical_node = self._build_technical_node_signal(close_series, high_series, low_series, volume_series, current_price)
            node_results.append(technical_node)
            if technical_node['available']:
                available_nodes += 1

        if self._is_trade_flow_enabled():
            enabled_nodes += 1
            trade_flow_node = self._build_trade_flow_node_signal(market_data.get('feeds', {}), current_price)
            node_results.append(trade_flow_node)
            if trade_flow_node['available']:
                available_nodes += 1

        if bool(self.config.get('enable_kline_breakout_node', False)):
            enabled_nodes += 1
            breakout_node = self._build_kline_breakout_node_signal(close_series, high_series, low_series, volume_series, current_price)
            node_results.append(breakout_node)
            if breakout_node['available']:
                available_nodes += 1

        if self._is_kline_trend_breakout_node_enabled():
            enabled_nodes += 1
            trend_breakout_node = self._build_kline_trend_breakout_node_signal(market_data, current_price)
            node_results.append(trend_breakout_node)
            if trend_breakout_node['available']:
                available_nodes += 1

        min_enabled_nodes = int(self.config.get('min_enabled_nodes', 1))
        degraded = available_nodes < enabled_nodes
        serialized_nodes = [self._serialize_node(item) for item in node_results]
        if available_nodes < min_enabled_nodes:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '可用信号节点不足，暂不交易',
                'strategy': self.name,
                'asof': market_data.get('decisionTimestamp') or market_data.get('timestamp'),
                'signal_sources': serialized_nodes,
                'signal_score': 0.0,
                'degraded': True,
                'meta': {
                    'enabled_node_count': enabled_nodes,
                    'available_node_count': available_nodes,
                    'node_signals': serialized_nodes,
                },
            }
        if degraded and not bool(self.config.get('allow_degraded', True)):
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '部分必需信号节点缺失，暂不交易',
                'strategy': self.name,
                'asof': market_data.get('decisionTimestamp') or market_data.get('timestamp'),
                'signal_sources': serialized_nodes,
                'signal_score': 0.0,
                'degraded': True,
                'meta': {
                    'enabled_node_count': enabled_nodes,
                    'available_node_count': available_nodes,
                    'node_signals': serialized_nodes,
                },
            }

        aggregate = self._aggregate_nodes(node_results)
        action = aggregate['action']
        confidence = aggregate['confidence']
        signal_score = aggregate['signal_score']
        atr_period = int(self.config.get('shared_atr_period', 14))
        atr_value = float(self._calculate_atr(high_series, low_series, close_series, atr_period).iloc[-1])
        if atr_value <= 0:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': 'ATR结果异常，暂不交易',
                'strategy': self.name,
                'asof': market_data.get('decisionTimestamp') or market_data.get('timestamp'),
                'signal_sources': serialized_nodes,
                'signal_score': signal_score,
                'degraded': degraded,
                'meta': {
                    **aggregate['meta'],
                    'node_signals': serialized_nodes,
                },
            }

        stop_loss_price = None
        trailing_stop_price = None
        atr_stop_mult = float(self.config.get('shared_atr_stop_mult', 2.0))
        atr_trail_mult = float(self.config.get('shared_atr_trail_mult', 3.0))
        if action == 'buy' and not position:
            stop_loss_price = current_price - atr_value * atr_stop_mult
            trailing_stop_price = stop_loss_price
        elif position:
            entry_price = float(position.get('entry_price', current_price))
            highest_close = max(float(position.get('highest_close', entry_price)), current_price)
            initial_stop_loss = float(position.get('initial_stop_loss', entry_price - atr_value * atr_stop_mult))
            trailing_stop_price = highest_close - atr_value * atr_trail_mult
            stop_loss_price = max(initial_stop_loss, trailing_stop_price)

        result = {
            'action': action,
            'confidence': confidence,
            'reason': aggregate['reason'],
            'strategy': self.name,
            'risk_per_trade': float(self.config.get('default_risk_per_trade', 0.01)),
            'stop_loss_price': stop_loss_price,
            'trailing_stop_price': trailing_stop_price,
            'asof': market_data.get('decisionTimestamp') or market_data.get('timestamp'),
            'signal_sources': serialized_nodes,
            'signal_score': signal_score,
            'degraded': degraded,
            'meta': {
                **aggregate['meta'],
                'signal_sources': serialized_nodes,
                'node_signals': serialized_nodes,
                'signal_score': signal_score,
                'degraded': degraded,
                'enabled_node_count': enabled_nodes,
                'available_node_count': available_nodes,
                'atr': atr_value,
                'market_price': current_price,
            },
        }
        if action == 'buy' and stop_loss_price is not None:
            result['stop_loss_pct'] = (current_price - stop_loss_price) / current_price if current_price > 0 else 0.0
        return result

    def _build_technical_node_signal(
        self,
        close_series: pd.Series,
        high_series: pd.Series,
        low_series: pd.Series,
        volume_series: pd.Series,
        current_price: float,
    ) -> Dict[str, Any]:
        ema_period = int(self.config.get('technical_ema_period', 55))
        breakout_lookback = int(self.config.get('technical_breakout_lookback', 20))
        rsi_buy_max = float(self.config.get('technical_rsi_buy_max', 68))
        rsi_sell_min = float(self.config.get('technical_rsi_sell_min', 52))
        require_macd = bool(self.config.get('technical_require_macd', True))

        ema_series = close_series.ewm(span=ema_period, adjust=False).mean()
        ema_now = float(ema_series.iloc[-1])
        breakout_high = float(high_series.iloc[-breakout_lookback - 1:-1].max())
        breakout_low = float(low_series.iloc[-breakout_lookback - 1:-1].min())
        rsi_value = float(self._calculate_rsi(close_series, 14).iloc[-1])
        fast_ema = close_series.ewm(span=12, adjust=False).mean()
        slow_ema = close_series.ewm(span=26, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = float((macd_line - macd_signal).iloc[-1])
        volume_ma = float(volume_series.rolling(window=min(20, len(volume_series))).mean().iloc[-1])
        current_volume = float(volume_series.iloc[-1])

        buy_score = 0.0
        buy_reasons = []
        if current_price > ema_now:
            buy_score += 0.25
            buy_reasons.append('价格站上EMA')
        if current_price > breakout_high:
            buy_score += 0.4
            buy_reasons.append('突破前高')
        if rsi_value <= rsi_buy_max:
            buy_score += 0.15
            buy_reasons.append('RSI未过热')
        if not require_macd or macd_histogram > 0:
            buy_score += 0.1
            buy_reasons.append('MACD偏多')
        if current_volume >= volume_ma:
            buy_score += 0.1
            buy_reasons.append('成交量不弱')

        sell_score = 0.0
        sell_reasons = []
        if current_price < ema_now:
            sell_score += 0.25
            sell_reasons.append('价格跌破EMA')
        if current_price < breakout_low:
            sell_score += 0.4
            sell_reasons.append('跌破近期低点')
        if rsi_value >= rsi_sell_min:
            sell_score += 0.15
            sell_reasons.append('RSI转弱')
        if macd_histogram < 0:
            sell_score += 0.1
            sell_reasons.append('MACD转空')
        if current_volume >= volume_ma:
            sell_score += 0.1
            sell_reasons.append('下跌伴随放量')

        bias = 'hold'
        bias_score = 0.0
        bias_reason = '技术面中性'
        if buy_score >= sell_score and buy_score > 0:
            bias = 'buy'
            bias_score = min(buy_score, 1.0)
            bias_reason = '、'.join(buy_reasons) or '技术面偏多'
        elif sell_score > buy_score and sell_score > 0:
            bias = 'sell'
            bias_score = min(sell_score, 1.0)
            bias_reason = '、'.join(sell_reasons) or '技术面偏空'

        return {
            'name': 'technical_node',
            'enabled': True,
            'available': True,
            'weight': float(self.config.get('technical_weight', 0.6)),
            'bias': bias,
            'score': bias_score,
            'confidence': bias_score,
            'reason': bias_reason,
            'meta': {
                'ema': ema_now,
                'breakout_high': breakout_high,
                'breakout_low': breakout_low,
                'rsi': rsi_value,
                'macd_histogram': macd_histogram,
                'current_volume': current_volume,
                'volume_ma': volume_ma,
            },
        }

    def _build_trade_flow_node_signal(self, feeds: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        payload = dict((feeds or {}).get('trade_flow') or {})
        available = bool(payload.get('available'))
        if not available:
            logging.info('融合策略未获取到可用 trade_flow feed，降级为可选缺失')
            return {
                'name': 'trade_flow_node',
                'enabled': True,
                'available': False,
                'weight': float(self.config.get('trade_flow_weight', 0.4)),
                'bias': 'hold',
                'score': 0.0,
                'confidence': 0.0,
                'reason': str(payload.get('reason') or 'trade_flow 数据缺失'),
                'meta': payload,
            }

        trade_payload = dict(payload.get('payload') or {})
        buy_ratio = float(trade_payload.get('buy_ratio') or 0.0)
        imbalance = float(trade_payload.get('notional_imbalance') or 0.0)
        latest_price = float(trade_payload.get('latest_price') or current_price)
        buy_threshold = float(self.config.get('trade_flow_buy_ratio_threshold', 0.55))
        sell_threshold = float(self.config.get('trade_flow_sell_ratio_threshold', 0.45))
        imbalance_threshold = float(self.config.get('trade_flow_imbalance_threshold', 0.08))

        if buy_ratio >= buy_threshold and imbalance >= imbalance_threshold:
            return {
                'name': 'trade_flow_node',
                'enabled': True,
                'available': True,
                'weight': float(self.config.get('trade_flow_weight', 0.4)),
                'bias': 'buy',
                'score': min(max(buy_ratio, imbalance), 1.0),
                'confidence': min(max(buy_ratio, imbalance), 1.0),
                'reason': '主动买盘占优',
                'meta': {
                    **trade_payload,
                    'latest_price': latest_price,
                },
            }
        if buy_ratio <= sell_threshold and imbalance <= -imbalance_threshold:
            return {
                'name': 'trade_flow_node',
                'enabled': True,
                'available': True,
                'weight': float(self.config.get('trade_flow_weight', 0.4)),
                'bias': 'sell',
                'score': min(max(1 - buy_ratio, abs(imbalance)), 1.0),
                'confidence': min(max(1 - buy_ratio, abs(imbalance)), 1.0),
                'reason': '主动卖盘占优',
                'meta': {
                    **trade_payload,
                    'latest_price': latest_price,
                },
            }
        return {
            'name': 'trade_flow_node',
            'enabled': True,
            'available': True,
            'weight': float(self.config.get('trade_flow_weight', 0.4)),
            'bias': 'hold',
            'score': 0.0,
            'confidence': 0.0,
            'reason': '成交流未形成明显倾向',
            'meta': {
                **trade_payload,
                'latest_price': latest_price,
            },
        }

    def _build_kline_breakout_node_signal(
        self,
        close_series: pd.Series,
        high_series: pd.Series,
        low_series: pd.Series,
        volume_series: pd.Series,
        current_price: float,
    ) -> Dict[str, Any]:
        donchian_entry = int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['donchian_entry'])
        donchian_exit = int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['donchian_exit'])
        ema_period = int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['ema_period'])
        ema_slope_lookback = int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['ema_slope_lookback'])
        volume_ma_period = int(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG['volume_ma_period'])
        confirm_macd = bool(self.config.get('kline_breakout_confirm_macd', True))
        confirm_volume = bool(self.config.get('kline_breakout_confirm_volume', True))
        volume_multiplier = float(self.config.get('kline_breakout_volume_multiplier', 1.1))
        breakout_buffer_bps = float(self.config.get('kline_breakout_breakout_buffer_bps', 10))

        ema_series = close_series.ewm(span=ema_period, adjust=False).mean()
        ema_now = float(ema_series.iloc[-1])
        ema_prev = float(ema_series.iloc[-1 - ema_slope_lookback])
        ema_slope_positive = ema_now > ema_prev
        ema_slope_negative = ema_now < ema_prev

        fast_ema = close_series.ewm(span=12, adjust=False).mean()
        slow_ema = close_series.ewm(span=26, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = float((macd_line - macd_signal).iloc[-1])

        current_volume = float(volume_series.iloc[-1])
        volume_ma = float(volume_series.rolling(window=volume_ma_period).mean().iloc[-1])
        entry_channel_high = float(high_series.iloc[-donchian_entry - 1:-1].max())
        exit_channel_low = float(low_series.iloc[-donchian_exit - 1:-1].min())
        breakout_price = entry_channel_high * (1 + breakout_buffer_bps / 10000)

        buy_score = 0.0
        buy_reasons = []
        if current_price > breakout_price:
            buy_score += 0.45
            buy_reasons.append('突破Donchian上轨')
        if current_price > ema_now and ema_slope_positive:
            buy_score += 0.25
            buy_reasons.append('趋势过滤通过')
        if not confirm_macd or macd_histogram > 0:
            buy_score += 0.15
            buy_reasons.append('MACD确认通过')
        if not confirm_volume or current_volume > volume_ma * volume_multiplier:
            buy_score += 0.15
            buy_reasons.append('量能确认通过')

        sell_score = 0.0
        sell_reasons = []
        if current_price < exit_channel_low:
            sell_score += 0.45
            sell_reasons.append('跌破Donchian下轨')
        if current_price < ema_now and ema_slope_negative:
            sell_score += 0.25
            sell_reasons.append('趋势转弱')
        if not confirm_macd or macd_histogram < 0:
            sell_score += 0.15
            sell_reasons.append('MACD转空')
        if not confirm_volume or current_volume > volume_ma * volume_multiplier:
            sell_score += 0.15
            sell_reasons.append('下跌伴随放量')

        bias = 'hold'
        score = 0.0
        reason = 'K线突破节点中性'
        if buy_score >= sell_score and buy_score > 0:
            bias = 'buy'
            score = min(buy_score, 1.0)
            reason = '、'.join(buy_reasons) or 'K线突破偏多'
        elif sell_score > buy_score and sell_score > 0:
            bias = 'sell'
            score = min(sell_score, 1.0)
            reason = '、'.join(sell_reasons) or 'K线突破偏空'

        return {
            'name': 'kline_breakout_node',
            'enabled': True,
            'available': True,
            'weight': float(self.config.get('kline_breakout_weight', 0.5)),
            'bias': bias,
            'score': score,
            'confidence': score,
            'reason': reason,
            'meta': {
                'entry_channel_high': entry_channel_high,
                'exit_channel_low': exit_channel_low,
                'breakout_price': breakout_price,
                'ema': ema_now,
                'ema_prev': ema_prev,
                'macd_histogram': macd_histogram,
                'volume_ma': volume_ma,
                'current_volume': current_volume,
            },
        }

    def _build_kline_trend_breakout_node_signal(self, market_data: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        primary_data = market_data.get('primary') or market_data
        context_data = (market_data.get('contexts') or {}).get('4h') or {}
        closes = primary_data.get('closes', [])
        highs = primary_data.get('highs', [])
        lows = primary_data.get('lows', [])
        volumes = primary_data.get('volumes', [])
        trend_closes = context_data.get('closes', [])
        trend_highs = context_data.get('highs', [])
        trend_lows = context_data.get('lows', [])

        required_trend_history = self.get_required_context_history().get('4h', 0)
        if len(trend_closes) < required_trend_history:
            return {
                'name': 'kline_trend_breakout_node',
                'enabled': True,
                'available': False,
                'weight': float(self.config.get('kline_trend_breakout_weight', 0.5)),
                'bias': 'hold',
                'score': 0.0,
                'confidence': 0.0,
                'reason': f'4h 趋势过滤所需K线不足，至少需要 {required_trend_history} 根',
                'meta': {
                    'required_trend_history': required_trend_history,
                    'current_trend_history': len(trend_closes),
                },
            }

        close_series = pd.Series(closes, dtype='float64')
        high_series = pd.Series(highs, dtype='float64')
        low_series = pd.Series(lows, dtype='float64')
        volume_series = pd.Series(volumes, dtype='float64')
        trend_close_series = pd.Series(trend_closes, dtype='float64')
        trend_high_series = pd.Series(trend_highs, dtype='float64')
        trend_low_series = pd.Series(trend_lows, dtype='float64')

        ema_fast_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['ema_fast_period'])
        ema_slow_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['ema_slow_period'])
        adx_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['adx_period'])
        breakout_lookback = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['breakout_lookback'])
        volume_ma_period = int(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG['volume_ma_period'])
        adx_threshold = float(self.config.get('kline_trend_breakout_adx_threshold', 25))
        volume_multiplier = float(self.config.get('kline_trend_breakout_volume_multiplier', 1.0))

        trend_ema_fast = float(trend_close_series.ewm(span=ema_fast_period, adjust=False).mean().iloc[-1])
        trend_ema_slow = float(trend_close_series.ewm(span=ema_slow_period, adjust=False).mean().iloc[-1])
        trend_adx = float(self._calculate_adx(trend_high_series, trend_low_series, trend_close_series, adx_period).iloc[-1])
        breakout_high = float(high_series.iloc[-breakout_lookback - 1:-1].max())
        breakout_low = float(low_series.iloc[-breakout_lookback - 1:-1].min())
        current_volume = float(volume_series.iloc[-1])
        volume_ma = float(volume_series.rolling(window=volume_ma_period).mean().iloc[-1])

        trend_ok = trend_ema_fast > trend_ema_slow and trend_adx >= adx_threshold
        trend_weak = trend_ema_fast < trend_ema_slow or trend_adx < adx_threshold
        breakout_ok = current_price > breakout_high
        breakdown_ok = current_price < breakout_low
        volume_ok = current_volume > volume_ma * volume_multiplier

        buy_score = 0.0
        buy_reasons = []
        if trend_ok:
            buy_score += 0.45
            buy_reasons.append('4h趋势过滤通过')
        if breakout_ok:
            buy_score += 0.35
            buy_reasons.append('1h突破前高')
        if volume_ok:
            buy_score += 0.2
            buy_reasons.append('1h放量确认')

        sell_score = 0.0
        sell_reasons = []
        if trend_weak:
            sell_score += 0.45
            sell_reasons.append('4h趋势转弱')
        if breakdown_ok:
            sell_score += 0.35
            sell_reasons.append('1h跌破低点')
        if volume_ok:
            sell_score += 0.2
            sell_reasons.append('下跌伴随放量')

        bias = 'hold'
        score = 0.0
        reason = '趋势突破节点中性'
        if buy_score >= sell_score and buy_score > 0:
            bias = 'buy'
            score = min(buy_score, 1.0)
            reason = '、'.join(buy_reasons) or '趋势突破偏多'
        elif sell_score > buy_score and sell_score > 0:
            bias = 'sell'
            score = min(sell_score, 1.0)
            reason = '、'.join(sell_reasons) or '趋势突破偏空'

        return {
            'name': 'kline_trend_breakout_node',
            'enabled': True,
            'available': True,
            'weight': float(self.config.get('kline_trend_breakout_weight', 0.5)),
            'bias': bias,
            'score': score,
            'confidence': score,
            'reason': reason,
            'meta': {
                'trend_ema_fast': trend_ema_fast,
                'trend_ema_slow': trend_ema_slow,
                'trend_adx': trend_adx,
                'breakout_high': breakout_high,
                'breakout_low': breakout_low,
                'volume_ma': volume_ma,
                'current_volume': current_volume,
            },
        }

    def _is_trade_flow_enabled(self, trade_flow_config: Optional[Dict[str, Any]] = None) -> bool:
        config = trade_flow_config if trade_flow_config is not None else dict(self.market_feeds_config.get('trade_flow') or {})
        return bool(self.config.get('enable_trade_flow_node', True)) and bool(config.get('enabled', True))

    def _is_kline_trend_breakout_node_enabled(self) -> bool:
        return bool(self.config.get('enable_kline_trend_breakout_node', False))

    def _aggregate_nodes(self, node_results: list[Dict[str, Any]]) -> Dict[str, Any]:
        buy_score = 0.0
        sell_score = 0.0
        active_nodes = []
        buy_nodes = []
        sell_nodes = []
        for item in node_results:
            if not item['available']:
                continue
            active_nodes.append(item)
            weighted_score = float(item['weight']) * float(item['score'])
            if item['bias'] == 'buy':
                buy_score += weighted_score
                buy_nodes.append(item['name'])
            elif item['bias'] == 'sell':
                sell_score += weighted_score
                sell_nodes.append(item['name'])

        buy_threshold = float(self.config.get('buy_threshold', 0.55))
        sell_threshold = float(self.config.get('sell_threshold', 0.55))
        min_confidence = float(self.config.get('min_confidence', 0.55))
        total_weight = sum(float(item['weight']) for item in active_nodes) or 1.0
        normalized_buy = buy_score / total_weight
        normalized_sell = sell_score / total_weight

        if normalized_buy >= buy_threshold and normalized_buy >= normalized_sell and normalized_buy >= min_confidence:
            return {
                'action': 'buy',
                'confidence': min(normalized_buy, 1.0),
                'signal_score': normalized_buy,
                'reason': '多源节点综合偏多',
                'meta': {
                    'normalized_buy_score': normalized_buy,
                    'normalized_sell_score': normalized_sell,
                    'active_buy_nodes': buy_nodes,
                    'active_sell_nodes': sell_nodes,
                },
            }
        if normalized_sell >= sell_threshold and normalized_sell > normalized_buy and normalized_sell >= min_confidence:
            return {
                'action': 'sell',
                'confidence': min(normalized_sell, 1.0),
                'signal_score': normalized_sell,
                'reason': '多源节点综合偏空',
                'meta': {
                    'normalized_buy_score': normalized_buy,
                    'normalized_sell_score': normalized_sell,
                    'active_buy_nodes': buy_nodes,
                    'active_sell_nodes': sell_nodes,
                },
            }
        return {
            'action': 'hold',
            'confidence': max(normalized_buy, normalized_sell, 0.0),
            'signal_score': max(normalized_buy, normalized_sell, 0.0),
            'reason': '多源节点未达到交易阈值',
            'meta': {
                'normalized_buy_score': normalized_buy,
                'normalized_sell_score': normalized_sell,
                'active_buy_nodes': buy_nodes,
                'active_sell_nodes': sell_nodes,
            },
        }

    @staticmethod
    def _serialize_node(item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'name': item.get('name'),
            'enabled': bool(item.get('enabled', True)),
            'available': bool(item.get('available')),
            'bias': item.get('bias', 'hold'),
            'score': float(item.get('score') or 0.0),
            'confidence': float(item.get('confidence') or 0.0),
            'weight': float(item.get('weight') or 0.0),
            'reason': item.get('reason', ''),
        }

    @staticmethod
    def _calculate_rsi(close_series: pd.Series, period: int) -> pd.Series:
        delta = close_series.diff().fillna(0.0)
        gains = delta.clip(lower=0)
        losses = -delta.clip(upper=0)
        average_gain = gains.rolling(window=period).mean().bfill()
        average_loss = losses.rolling(window=period).mean().bfill()
        loss_denominator = average_loss.mask(average_loss == 0)
        rs = average_gain / loss_denominator
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def _calculate_atr(high_series: pd.Series, low_series: pd.Series, close_series: pd.Series, period: int) -> pd.Series:
        previous_close = close_series.shift(1)
        true_range = pd.concat(
            [
                high_series - low_series,
                (high_series - previous_close).abs(),
                (low_series - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.rolling(window=period).mean().bfill()

    @staticmethod
    def _calculate_adx(high_series: pd.Series, low_series: pd.Series, close_series: pd.Series, period: int) -> pd.Series:
        up_move = high_series.diff()
        down_move = -low_series.diff()
        plus_dm = pd.Series(
            [up if up > down and up > 0 else 0.0 for up, down in zip(up_move, down_move)],
            index=high_series.index,
            dtype='float64',
        )
        minus_dm = pd.Series(
            [down if down > up and down > 0 else 0.0 for up, down in zip(up_move, down_move)],
            index=high_series.index,
            dtype='float64',
        )
        atr = SpotMultiSignalFusionStrategy._calculate_atr(high_series, low_series, close_series, period)
        plus_di = (plus_dm.rolling(window=period).mean() / atr.replace(0, pd.NA)) * 100
        minus_di = (minus_dm.rolling(window=period).mean() / atr.replace(0, pd.NA)) * 100
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)) * 100
        return dx.rolling(window=period).mean().bfill().fillna(0.0)
