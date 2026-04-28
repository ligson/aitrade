import logging
from datetime import datetime
from typing import Any, Dict, List

import ccxt
import numpy as np
import pandas as pd


class MarketDataFetcher:
    """市场数据获取器。"""

    def __init__(self, exchange_type: str, api_key: str, secret: str, password: str = '', sandbox: bool = True, proxies: Dict[str, str] = None):
        ccxt_cfg = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        }

        if exchange_type == "okx" and password:
            ccxt_cfg['password'] = password

        if proxies:
            ccxt_cfg['proxies'] = proxies

        if exchange_type == "binance":
            ccxt_cfg['options'] = {
                'defaultType': 'spot',
                'fetchMarkets': {
                    'types': ['spot'],
                },
            }
            self.exchange = ccxt.binance(ccxt_cfg)
            logging.info("初始化Binance交易所，沙盒模式: %s", sandbox)
        else:
            self.exchange = ccxt.okx(ccxt_cfg)
            logging.info("初始化OKX交易所，沙盒模式: %s", sandbox)

        if sandbox and hasattr(self.exchange, 'set_sandbox_mode'):
            self.exchange.set_sandbox_mode(True)

        try:
            self.exchange.load_markets()
            logging.debug("成功加载交易所市场数据")
        except Exception as e:
            logging.error("加载市场数据失败: %s", e)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]:
        try:
            logging.debug("获取 %s 的 %s OHLCV数据，条数: %s", symbol, timeframe, limit)
            markets = self.exchange.markets
            if not markets:
                logging.info("交易所市场列表为空，尝试重新加载")
                markets = self.exchange.load_markets()

            if symbol not in markets:
                available_symbols = list(markets.keys())
                logging.warning("交易对 %s 不在可用市场列表中，可用交易对数量: %s", symbol, len(available_symbols))
                if available_symbols:
                    logging.debug("部分可用交易对示例: %s", available_symbols[:10])

            data = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            logging.info("成功获取 %s 条OHLCV数据", len(data))
            return data
        except Exception as e:
            logging.error("获取OHLCV数据失败: %s", e)
            raise

    def get_enhanced_market_data(self, symbol: str = 'BTC/USDT', timeframe: str = '15m', limit: int = 100) -> Dict[str, Any]:
        logging.info("获取 %s 的增强市场数据", symbol)
        ohlcv = self.fetch_ohlcv(symbol, timeframe, limit)

        timestamps = [c[0] for c in ohlcv]
        opens = [c[1] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        technicals = self._calculate_technical_indicators(closes, highs, lows, volumes)
        market_data = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': closes[-1],
            'timestamps': timestamps,
            'opens': opens,
            'highs': highs,
            'lows': lows,
            'closes': closes,
            'volumes': volumes,
            'ohlcv': ohlcv,
            'technicals': technicals,
        }

        logging.debug("市场数据获取完成，当前价格: %s", closes[-1])
        return market_data

    def fetch_recent_trades(self, symbol: str, limit: int = 200) -> List[Dict[str, Any]]:
        try:
            logging.info("获取 %s 的近期成交数据，条数: %s", symbol, limit)
            trades = self.exchange.fetch_trades(symbol, limit=limit)
            logging.info("成功获取 %s 条成交数据", len(trades))
            return trades
        except Exception as exc:
            logging.error("获取近期成交数据失败: symbol=%s limit=%s error=%s", symbol, limit, exc)
            raise

    def _calculate_technical_indicators(self, closes: List[float], highs: List[float], lows: List[float], volumes: List[float]) -> Dict[str, Any]:
        logging.debug("开始计算技术指标")

        def compute_rsi(prices, period=14):
            deltas = np.diff(prices)
            if len(deltas) < period:
                return np.array([50.0])

            seed = deltas[:period]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            rs = up / (down + 1e-10)
            rsi = np.array([100 - (100 / (1 + rs))])

            for i in range(period, len(deltas)):
                delta = deltas[i]
                up = (up * (period - 1) + max(delta, 0)) / period
                down = (down * (period - 1) + max(-delta, 0)) / period
                rs = up / (down + 1e-10)
                rsi = np.append(rsi, 100 - (100 / (1 + rs)))

            return rsi

        ema12 = pd.Series(closes).ewm(span=12).mean().values
        ema26 = pd.Series(closes).ewm(span=26).mean().values
        macd_line = ema12 - ema26
        signal_line = pd.Series(macd_line).ewm(span=9).mean().values
        macd_histogram = macd_line - signal_line

        lookback = min(20, len(highs))
        recent_high = max(highs[-lookback:])
        recent_low = min(lows[-lookback:])
        volume_avg = np.mean(volumes[-lookback:])
        price_ma = np.mean(closes[-lookback:])
        volume_trend = "上升" if volumes[-1] > volume_avg else "下降"

        technicals = {
            'rsi': float(compute_rsi(closes)[-1]) if len(closes) > 14 else 50,
            'macd_line': float(macd_line[-1]),
            'macd_signal': float(signal_line[-1]),
            'macd_histogram': float(macd_histogram[-1]),
            'macd_trend': "bullish" if macd_histogram[-1] > 0 else "bearish",
            'resistance': float(recent_high),
            'support': float(recent_low),
            'volume_trend': volume_trend,
            'price_vs_ma': "above" if closes[-1] > price_ma else "below",
        }

        logging.info("技术指标计算完成 - RSI: %.2f, MACD: %.4f", technicals['rsi'], technicals['macd_histogram'])
        return technicals
