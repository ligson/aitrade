import ccxt
import numpy as np
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, List


class MarketDataFetcher:
    """市场数据获取器
    
    负责从交易所获取市场数据，包括OHLCV数据和计算技术指标。
    支持多种交易所和代理设置。
    
    Attributes:
        exchange: CCXT交易所实例
    """

    def __init__(self, exchange_type: str, api_key: str, secret: str, sandbox: bool = True, proxies: Dict[str, str] = None):
        """
        初始化市场数据获取器
        
        Args:
            exchange_type (str): 交易所类型 ('binance', 'okx')
            api_key (str): API密钥
            secret (str): API密钥
            sandbox (bool): 是否使用沙盒模式，默认为True
            proxies (Dict[str, str], optional): 代理设置
            
        Example:
            >>> fetcher = MarketDataFetcher('binance', 'your_api_key', 'your_secret', True)
        """
        ccxt_cfg = {
            'apiKey': api_key,
            'secret': secret,
            'sandbox': sandbox,
            'enableRateLimit': True
        }

        if proxies:
            ccxt_cfg['proxies'] = proxies

        # 根据交易所类型初始化相应的交易所实例
        if exchange_type == "binance":
            self.exchange = ccxt.binance(ccxt_cfg)
            logging.info(f"初始化Binance交易所，沙盒模式: {sandbox}")
        else:
            self.exchange = ccxt.okx(ccxt_cfg)
            logging.info(f"初始化OKX交易所，沙盒模式: {sandbox}")
            
        # 加载市场数据
        try:
            self.exchange.load_markets()
            logging.debug("成功加载交易所市场数据")
        except Exception as e:
            logging.error(f"加载市场数据失败: {e}")

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> List[List[float]]:
        """
        获取OHLCV数据（开盘价、最高价、最低价、收盘价、成交量）
        
        Args:
            symbol (str): 交易对，例如 'BTC/USDT'
            timeframe (str): 时间周期，例如 '15m', '1h', '1d'
            limit (int): 获取的数据条数
            
        Returns:
            List[List[float]]: OHLCV数据列表，每个元素包含[时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量]
            
        Raises:
            Exception: 当获取数据失败时抛出异常
            
        Example:
            >>> data = fetcher.fetch_ohlcv('BTC/USDT', '1h', 100)
            >>> print(len(data))
            100
        """
        try:
            logging.debug(f"获取 {symbol} 的 {timeframe} OHLCV数据，条数: {limit}")
            data = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            logging.info(f"成功获取 {len(data)} 条OHLCV数据")
            return data
        except Exception as e:
            logging.error(f"获取OHLCV数据失败: {e}")
            raise

    def get_enhanced_market_data(self, symbol: str = 'BTC/USDT', timeframe: str = '15m', limit: int = 100) -> Dict[str, Any]:
        """
        获取增强的市场数据，包括价格、成交量和技术指标
        
        这个方法整合了价格数据、历史数据和各种技术指标，为后续的交易决策提供全面的市场信息。
        
        Args:
            symbol (str): 交易对，默认为'BTC/USDT'
            timeframe (str): 时间周期，默认为'15m'
            limit (int): 数据条数，默认为100
            
        Returns:
            Dict[str, Any]: 包含市场数据和技术指标的字典，结构如下:
            {
                'symbol': 交易对名称,
                'timestamp': 数据获取时间,
                'price': 当前价格,
                'closes': 收盘价列表,
                'volumes': 成交量列表,
                'technicals': 各种技术指标
            }
            
        Example:
            >>> market_data = fetcher.get_enhanced_market_data('ETH/USDT', '1h', 50)
            >>> print(market_data['price'])
        """
        logging.info(f"获取 {symbol} 的增强市场数据")
        
        # 获取OHLCV数据
        ohlcv = self.fetch_ohlcv(symbol, timeframe, limit)
        
        # 提取各列数据
        closes = [c[4] for c in ohlcv]  # 收盘价
        volumes = [c[5] for c in ohlcv]  # 成交量
        highs = [c[2] for c in ohlcv]    # 最高价
        lows = [c[3] for c in ohlcv]     # 最低价

        # 计算技术指标
        technicals = self._calculate_technical_indicators(closes, highs, lows, volumes)
        
        # 构建市场数据字典
        market_data = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': closes[-1],
            'closes': closes,
            'volumes': volumes,
            'technicals': technicals
        }
        
        logging.debug(f"市场数据获取完成，当前价格: {closes[-1]}")
        return market_data

    def _calculate_technical_indicators(self, closes: List[float], highs: List[float], lows: List[float], volumes: List[float]) -> Dict[str, Any]:
        """
        计算技术指标
        
        计算多种常用的技术指标，包括RSI、MACD、支撑阻力位等，用于辅助交易决策。
        
        Args:
            closes (List[float]): 收盘价列表
            highs (List[float]): 最高价列表
            lows (List[float]): 最低价列表
            volumes (List[float]): 成交量列表
            
        Returns:
            Dict[str, Any]: 技术指标字典，包含以下键值:
            - 'rsi': 相对强弱指数
            - 'macd_line': MACD线
            - 'macd_signal': MACD信号线
            - 'macd_histogram': MACD柱状图
            - 'macd_trend': MACD趋势判断
            - 'resistance': 阻力位
            - 'support': 支撑位
            - 'volume_trend': 成交量趋势
            - 'price_vs_ma': 价格与均线关系
        """
        logging.debug("开始计算技术指标")
        
        # RSI (相对强弱指数)
        def compute_rsi(prices, period=14):
            """计算RSI指标
            
            RSI是衡量资产价格变动速度和变化幅度的技术指标，
            通常用于识别超买或超卖状况。
            
            Args:
                prices: 价格序列
                period: 计算周期，默认14
                
            Returns:
                numpy.ndarray: RSI值数组
            """
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

        # MACD (异同移动平均线)
        # 快速EMA(12)和慢速EMA(26)
        ema12 = pd.Series(closes).ewm(span=12).mean().values
        ema26 = pd.Series(closes).ewm(span=26).mean().values
        macd_line = ema12 - ema26  # MACD线
        signal_line = pd.Series(macd_line).ewm(span=9).mean().values  # 信号线
        macd_histogram = macd_line - signal_line  # 柱状图

        # 支撑阻力位 - 基于最近20个周期的最高最低价
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])

        # 成交量分析
        volume_avg = np.mean(volumes[-20:])
        volume_trend = "上升" if volumes[-1] > volume_avg else "下降"

        # 构建技术指标字典
        technicals = {
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
        
        logging.info(f"技术指标计算完成 - RSI: {technicals['rsi']:.2f}, MACD: {technicals['macd_histogram']:.4f}")
        return technicals