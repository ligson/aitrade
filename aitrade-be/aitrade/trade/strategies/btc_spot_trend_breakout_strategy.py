import logging
from typing import Any, Dict, Optional

import pandas as pd

from .base_strategy import BaseStrategy


class BTCSpotTrendBreakoutStrategy(BaseStrategy):
    name = 'btc_spot_trend_breakout'

    def get_market_data_requirements(self) -> Dict[str, Any]:
        return {
            'primary_timeframe': '1h',
            'context_timeframes': ['4h'],
        }

    def get_required_history(self) -> int:
        return max(
            int(self.config.get('breakout_lookback', 20)) + 2,
            int(self.config.get('volume_ma_period', 20)) + 2,
            int(self.config.get('atr_period', 14)) + 2,
        )

    def get_required_context_history(self) -> Dict[str, int]:
        ema_slow_period = int(self.config.get('ema_slow_period', 50))
        adx_period = int(self.config.get('adx_period', 14))
        return {
            '4h': max(ema_slow_period + 2, adx_period * 2 + 2),
        }

    def generate_signal(self, market_data: Dict[str, Any], position: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        primary_data = market_data.get('primary') or market_data
        context_data = (market_data.get('contexts') or {}).get('4h') or {}

        closes = primary_data.get('closes', [])
        highs = primary_data.get('highs', [])
        lows = primary_data.get('lows', [])
        volumes = primary_data.get('volumes', [])
        trend_closes = context_data.get('closes', [])
        trend_highs = context_data.get('highs', [])
        trend_lows = context_data.get('lows', [])

        required_history = self.get_required_history()
        required_trend_history = self.get_required_context_history().get('4h', 0)
        if len(closes) < required_history:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'1h 规则所需K线不足，至少需要 {required_history} 根',
                'strategy': self.name,
                'meta': {
                    'required_history': required_history,
                    'current_history': len(closes),
                },
            }
        if len(trend_closes) < required_trend_history:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': f'4h 趋势过滤所需K线不足，至少需要 {required_trend_history} 根',
                'strategy': self.name,
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

        ema_fast_period = int(self.config.get('ema_fast_period', 20))
        ema_slow_period = int(self.config.get('ema_slow_period', 50))
        adx_period = int(self.config.get('adx_period', 14))
        adx_threshold = float(self.config.get('adx_threshold', 25))
        breakout_lookback = int(self.config.get('breakout_lookback', 20))
        volume_ma_period = int(self.config.get('volume_ma_period', 20))
        volume_multiplier = float(self.config.get('volume_multiplier', 1.0))
        atr_period = int(self.config.get('atr_period', 14))
        atr_stop_mult = float(self.config.get('atr_stop_mult', 2.0))
        atr_trail_mult = float(self.config.get('atr_trail_mult', 3.0))
        default_risk_per_trade = float(self.config.get('default_risk_per_trade', 0.01))

        trend_ema_fast = float(trend_close_series.ewm(span=ema_fast_period, adjust=False).mean().iloc[-1])
        trend_ema_slow = float(trend_close_series.ewm(span=ema_slow_period, adjust=False).mean().iloc[-1])
        trend_adx = float(self._calculate_adx(trend_high_series, trend_low_series, trend_close_series, adx_period).iloc[-1])

        current_price = float(close_series.iloc[-1])
        current_volume = float(volume_series.iloc[-1])
        breakout_high = float(high_series.iloc[-breakout_lookback - 1:-1].max())
        volume_ma = float(volume_series.rolling(window=volume_ma_period).mean().iloc[-1])
        atr_value = float(self._calculate_atr(high_series, low_series, close_series, atr_period).iloc[-1])

        meta = {
            'trend_ema_fast': trend_ema_fast,
            'trend_ema_slow': trend_ema_slow,
            'trend_adx': trend_adx,
            'breakout_high': breakout_high,
            'volume_ma': volume_ma,
            'current_volume': current_volume,
            'atr': atr_value,
        }

        if atr_value <= 0:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': 'ATR结果异常，暂不交易',
                'strategy': self.name,
                'meta': meta,
            }

        trend_ok = trend_ema_fast > trend_ema_slow and trend_adx >= adx_threshold
        breakout_ok = current_price > breakout_high
        volume_ok = current_volume > volume_ma * volume_multiplier

        if not position:
            if trend_ok and breakout_ok and volume_ok:
                stop_loss_price = current_price - atr_value * atr_stop_mult
                stop_loss_pct = (current_price - stop_loss_price) / current_price
                meta['effective_stop_loss'] = stop_loss_price
                meta['trailing_stop_price'] = stop_loss_price
                return {
                    'action': 'buy',
                    'confidence': 0.84,
                    'reason': '4h 趋势过滤通过，1h 突破并放量',
                    'strategy': self.name,
                    'stop_loss_pct': stop_loss_pct,
                    'stop_loss_price': stop_loss_price,
                    'trailing_stop_price': stop_loss_price,
                    'risk_per_trade': default_risk_per_trade,
                    'meta': meta,
                }

            failed_checks = []
            if not trend_ok:
                failed_checks.append('4h 趋势过滤未通过')
            if not breakout_ok:
                failed_checks.append('1h 未突破前高')
            if not volume_ok:
                failed_checks.append('1h 成交量未放大')
            return {
                'action': 'hold',
                'confidence': 0.28,
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
        if current_price <= initial_stop_loss:
            exit_reasons.append('跌破 ATR 初始止损')
        if current_price <= trailing_stop_price:
            exit_reasons.append('跌破 ATR 追踪止损')
        if not trend_ok:
            exit_reasons.append('4h 趋势过滤转弱')

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
            'confidence': 0.58,
            'reason': '持仓继续，按 ATR 追踪止损抬升保护位',
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
        atr = BTCSpotTrendBreakoutStrategy._calculate_atr(high_series, low_series, close_series, period)
        plus_di = (plus_dm.rolling(window=period).mean() / atr.replace(0, pd.NA)) * 100
        minus_di = (minus_dm.rolling(window=period).mean() / atr.replace(0, pd.NA)) * 100
        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)) * 100
        return dx.rolling(window=period).mean().bfill().fillna(0.0)
