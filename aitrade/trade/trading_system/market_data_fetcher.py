import ccxt
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List


class MarketDataFetcher:
    """市场数据获取器"""

    def __init__(self, exchange_type: str, api_key: str, secret: str, sandbox: bool = True, proxies: Dict[str, str] = None):
        """
        初始化市场数据获取器
        
        Args:
            exchange_type: 交易所类型 ('binance', 'okx')
            api_key: API密钥
            secret: API密钥
            sandbox: 是否使用沙盒模式
            proxies: 代理设置
        """
        ccxt_cfg = {
            'apiKey': api_key,
            'secret': secret,
            'sandbox': sandbox,
            'enableRateLimit': True
        }

        if proxies:
            ccxt_cfg['proxies'] = proxies

        if exchange_type == "binance":
            self.exchange = ccxt.binance(ccxt_cfg)
        else:
            self.exchange = ccxt.okx(ccxt_cfg)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]:
        """
        获取OHLCV数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            limit: 数据条数
            
        Returns:
            OHLCV数据列表
        """
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    def get_enhanced_market_data(self, symbol: str = 'BTC/USDT', timeframe: str = '15m', limit: int = 100) -> Dict[str, Any]:
        """
        获取增强的市场数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            limit: 数据条数
            
        Returns:
            包含价格、成交量和技术指标的市场数据字典
        """
        ohlcv = self.fetch_ohlcv(symbol, timeframe, limit)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]

        technicals = self._calculate_technical_indicators(closes, highs, lows, volumes)

        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': closes[-1],
            'closes': closes,
            'volumes': volumes,
            'technicals': technicals
        }

    def _calculate_technical_indicators(self, closes: List[float], highs: List[float], lows: List[float], volumes: List[float]) -> Dict[str, Any]:
        """
        计算技术指标
        
        Args:
            closes: 收盘价列表
            highs: 最高价列表
            lows: 最低价列表
            volumes: 成交量列表
            
        Returns:
            技术指标字典
        """
        # RSI
        def compute_rsi(prices, period=14):
            deltas = np.diff(prices)
            seed = deltas[:period]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            rs = up / (down + 1e-10)
            rsi = 100 - (100 / (1 + rs))

            for i in range(period, len(deltas)):
                delta = deltas[i]
                up = (up * (period - 1) + max(delta, 0)) / period
                down = (down * (period - 1) + max(-delta, 0)) / period
                rs = up / (down + 1e-10)
                rsi = np.append(rsi, 100 - (100 / (1 + rs)))

            return rsi

        # MACD
        ema12 = pd.Series(closes).ewm(span=12).mean().values
        ema26 = pd.Series(closes).ewm(span=26).mean().values
        macd_line = ema12 - ema26
        signal_line = pd.Series(macd_line).ewm(span=9).mean().values
        macd_histogram = macd_line - signal_line

        # 支撑阻力
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])

        # 成交量分析
        volume_avg = np.mean(volumes[-20:])
        volume_trend = "上升" if volumes[-1] > volume_avg else "下降"

        return {
            'rsi': compute_rsi(closes)[-1] if len(closes) > 14 else 50,
            'macd_line': macd_line[-1],
            'macd_signal': signal_line[-1],
            'macd_histogram': macd_histogram[-1],
            'macd_trend': "bullish" if macd_histogram[-1] > 0 else "bearish",
            'resistance': recent_high,
            'support': recent_low,
            'volume_trend': volume_trend,
            'price_vs_ma': "above" if closes[-1] > np.mean(closes[-20:]) else "below"
        }