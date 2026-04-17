import logging
from typing import Any, Dict, Optional

import pandas as pd

from .base_strategy import BaseStrategy


class BTCSpotBreakoutStrategy(BaseStrategy):
    name = 'btc_spot_breakout'

    def get_required_history(self) -> int:
        return max(
            int(self.config.get('donchian_entry', 20)) + 2,
            int(self.config.get('donchian_exit', 10)) + 2,
            int(self.config.get('ema_period', 96)) + int(self.config.get('ema_slope_lookback', 4)) + 2,
            int(self.config.get('atr_period', 14)) + 2,
            int(self.config.get('volume_ma_period', 20)) + 2,
        )

    def generate_signal(self, market_data: Dict[str, Any], position: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        closes = market_data.get('closes', [])
        highs = market_data.get('highs', [])
        lows = market_data.get('lows', [])
        volumes = market_data.get('volumes', [])

        required_history = self.get_required_history()
        if len(closes) < required_history:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'规则策略所需K线不足，至少需要 {required_history} 根',
                'strategy': self.name,
                'meta': {
                    'required_history': required_history,
                    'current_history': len(closes),
                },
            }

        close_series = pd.Series(closes, dtype='float64')
        high_series = pd.Series(highs, dtype='float64')
        low_series = pd.Series(lows, dtype='float64')
        volume_series = pd.Series(volumes, dtype='float64')

        donchian_entry = int(self.config.get('donchian_entry', 20))
        donchian_exit = int(self.config.get('donchian_exit', 10))
        ema_period = int(self.config.get('ema_period', 96))
        ema_slope_lookback = int(self.config.get('ema_slope_lookback', 4))
        atr_period = int(self.config.get('atr_period', 14))
        atr_stop_mult = float(self.config.get('atr_stop_mult', 2.5))
        atr_trail_mult = float(self.config.get('atr_trail_mult', 3.0))
        breakout_buffer_bps = float(self.config.get('breakout_buffer_bps', 10))
        confirm_macd = bool(self.config.get('confirm_macd', True))
        confirm_volume = bool(self.config.get('confirm_volume', True))
        volume_ma_period = int(self.config.get('volume_ma_period', 20))
        volume_multiplier = float(self.config.get('volume_multiplier', 1.1))
        default_risk_per_trade = float(self.config.get('default_risk_per_trade', 0.01))

        ema_series = close_series.ewm(span=ema_period, adjust=False).mean()
        ema_now = float(ema_series.iloc[-1])
        ema_prev = float(ema_series.iloc[-1 - ema_slope_lookback])
        ema_slope_positive = ema_now > ema_prev

        fast_ema = close_series.ewm(span=12, adjust=False).mean()
        slow_ema = close_series.ewm(span=26, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - macd_signal
        macd_histogram_value = float(macd_histogram.iloc[-1])

        volume_ma = float(volume_series.rolling(window=volume_ma_period).mean().iloc[-1])
        atr_value = float(self._calculate_atr(high_series, low_series, close_series, atr_period).iloc[-1])

        current_price = float(close_series.iloc[-1])
        current_volume = float(volume_series.iloc[-1])
        entry_channel_high = float(high_series.iloc[-donchian_entry - 1:-1].max())
        exit_channel_low = float(low_series.iloc[-donchian_exit - 1:-1].min())
        breakout_price = entry_channel_high * (1 + breakout_buffer_bps / 10000)

        meta = {
            'entry_channel_high': entry_channel_high,
            'exit_channel_low': exit_channel_low,
            'breakout_price': breakout_price,
            'ema': ema_now,
            'ema_prev': ema_prev,
            'atr': atr_value,
            'macd_histogram': macd_histogram_value,
            'volume_ma': volume_ma,
            'current_volume': current_volume,
        }

        if atr_value <= 0:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': 'ATR结果异常，暂不交易',
                'strategy': self.name,
                'meta': meta,
            }

        trend_ok = current_price > ema_now and ema_slope_positive
        macd_ok = (not confirm_macd) or macd_histogram_value > 0
        volume_ok = (not confirm_volume) or current_volume > volume_ma * volume_multiplier
        breakout_ok = current_price > breakout_price

        if not position:
            if breakout_ok and trend_ok and macd_ok and volume_ok:
                stop_loss_price = current_price - atr_value * atr_stop_mult
                stop_loss_pct = (current_price - stop_loss_price) / current_price
                return {
                    'action': 'buy',
                    'confidence': 0.82,
                    'reason': 'Donchian突破、趋势与量能条件同时满足',
                    'strategy': self.name,
                    'stop_loss_pct': stop_loss_pct,
                    'stop_loss_price': stop_loss_price,
                    'risk_per_trade': default_risk_per_trade,
                    'meta': meta,
                }

            failed_checks = []
            if not breakout_ok:
                failed_checks.append('未突破上轨')
            if not trend_ok:
                failed_checks.append('趋势过滤未通过')
            if not macd_ok:
                failed_checks.append('MACD确认未通过')
            if not volume_ok:
                failed_checks.append('成交量确认未通过')

            return {
                'action': 'hold',
                'confidence': 0.25,
                'reason': '、'.join(failed_checks) or '规则条件未满足',
                'strategy': self.name,
                'meta': meta,
            }

        entry_price = float(position.get('entry_price', current_price))
        highest_price = max(float(position.get('highest_price', entry_price)), float(high_series.iloc[-1]), current_price)
        highest_close = max(float(position.get('highest_close', entry_price)), current_price)
        initial_stop_loss = float(position.get('initial_stop_loss', entry_price - atr_value * atr_stop_mult))
        trailing_stop_price = highest_close - atr_value * atr_trail_mult
        effective_stop_loss = max(initial_stop_loss, trailing_stop_price)

        meta.update({
            'highest_price': highest_price,
            'highest_close': highest_close,
            'initial_stop_loss': initial_stop_loss,
            'trailing_stop_price': trailing_stop_price,
            'effective_stop_loss': effective_stop_loss,
        })

        exit_reasons = []
        if current_price < exit_channel_low:
            exit_reasons.append('跌破Donchian出场下轨')
        if current_price <= initial_stop_loss:
            exit_reasons.append('跌破ATR初始止损')
        if current_price <= trailing_stop_price:
            exit_reasons.append('跌破ATR追踪止损')

        if exit_reasons:
            return {
                'action': 'sell',
                'confidence': 0.9,
                'reason': '、'.join(exit_reasons),
                'strategy': self.name,
                'stop_loss_price': effective_stop_loss,
                'trailing_stop_price': trailing_stop_price,
                'meta': meta,
            }

        return {
            'action': 'hold',
            'confidence': 0.55,
            'reason': '持仓继续，按追踪止损抬升保护位',
            'strategy': self.name,
            'stop_loss_price': effective_stop_loss,
            'trailing_stop_price': trailing_stop_price,
            'meta': meta,
        }

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
