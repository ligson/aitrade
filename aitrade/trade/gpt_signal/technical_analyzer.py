import numpy as np
import pandas as pd
import logging


class TechnicalAnalyzer:
    """技术指标分析器
    
    负责计算和分析各种技术指标，为AI交易信号生成提供数据支持。
    包括RSI、MACD、价格趋势和成交量分析等功能。
    """

    @staticmethod
    def compute_rsi(prices, period=14):
        """计算RSI指标
        
        相对强弱指数（RSI）是通过比较近期价格上涨和下跌的幅度来衡量价格变化的速度和变化量。
        
        Args:
            prices (list): 价格序列数据
            period (int): 计算周期，默认为14
            
        Returns:
            numpy.ndarray: RSI值数组
        """
        logging.debug(f"计算RSI指标，周期: {period}，数据点数: {len(prices)}")
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

        logging.debug(f"RSI计算完成，最新值: {rsi[-1]:.2f}")
        return rsi

    @staticmethod
    def analyze_rsi(rsi_value):
        """分析RSI指标状态
        
        根据RSI值判断市场超买超卖状态。
        
        Args:
            rsi_value (float): RSI指标值
            
        Returns:
            dict: 包含RSI分析结果的字典
        """
        logging.debug(f"分析RSI指标状态，当前值: {rsi_value}")
        rsi_analysis = {
            'value': rsi_value,
            'condition': 'neutral',
            'strength': 0,
            'details': ''
        }

        if rsi_value < 30:
            rsi_analysis.update({'condition': 'oversold', 'strength': min(1.0, (30 - rsi_value) / 30)})
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于超卖区域'
            logging.debug("RSI处于超卖状态")
        elif rsi_value > 70:
            rsi_analysis.update({'condition': 'overbought', 'strength': min(1.0, (rsi_value - 70) / 30)})
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于超买区域'
            logging.debug("RSI处于超买状态")
        else:
            rsi_analysis['strength'] = 0.5
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于中性区域'
            logging.debug("RSI处于中性状态")

        return rsi_analysis

    @staticmethod
    def analyze_macd(closes):
        """分析MACD指标
        
        异同移动平均线（MACD）用于判断价格趋势和动量。
        
        Args:
            closes (list): 收盘价序列
            
        Returns:
            tuple: (macd_analysis, macd_line, signal_line, macd_histogram)
        """
        logging.debug(f"分析MACD指标，数据点数: {len(closes)}")
        # 计算MACD相关值
        ema12 = pd.Series(closes).ewm(span=12).mean().values
        ema26 = pd.Series(closes).ewm(span=26).mean().values
        macd_line = ema12 - ema26
        signal_line = pd.Series(macd_line).ewm(span=9).mean().values
        macd_histogram = macd_line - signal_line

        # MACD分析
        macd_analysis = {
            'trend': 'neutral',
            'momentum': 0,
            'crossover': 'none',
            'details': ''
        }

        # MACD趋势判断
        if macd_histogram[-1] > 0:
            macd_analysis['trend'] = 'bullish'
            macd_analysis['momentum'] = min(1.0, float(macd_histogram[-1]) / (abs(float(macd_line[-1])) + 1e-10))
            logging.debug("MACD呈看涨趋势")
        else:
            macd_analysis['trend'] = 'bearish'
            macd_analysis['momentum'] = min(1.0, abs(float(macd_histogram[-1])) / (abs(float(macd_line[-1])) + 1e-10))
            logging.debug("MACD呈看跌趋势")

        # 金叉死叉判断
        if len(macd_line) >= 2 and len(signal_line) >= 2:
            # 检查是否发生金叉（MACD线上穿信号线）
            if macd_line[-2] <= signal_line[-2] and macd_line[-1] > signal_line[-1]:
                macd_analysis['crossover'] = 'golden'
                macd_analysis['details'] = 'MACD金叉，看涨信号'
                logging.info("检测到MACD金叉信号")
            # 检查是否发生死叉（MACD线下穿信号线）
            elif macd_line[-2] >= signal_line[-2] and macd_line[-1] < signal_line[-1]:
                macd_analysis['crossover'] = 'death'
                macd_analysis['details'] = 'MACD死叉，看跌信号'
                logging.info("检测到MACD死叉信号")
            else:
                macd_analysis['details'] = 'MACD无明显交叉信号'
                logging.debug("MACD无明显交叉信号")
        else:
            macd_analysis['details'] = '数据不足，无法判断交叉信号'
            logging.warning("数据不足，无法判断MACD交叉信号")

        logging.debug(f"MACD分析完成，趋势: {macd_analysis['trend']}, 动量: {macd_analysis['momentum']:.2f}")
        return macd_analysis, macd_line[-1], signal_line[-1], macd_histogram[-1]

    @staticmethod
    def analyze_price_trend(closes, short_period=10, long_period=20):
        """分析价格趋势
        
        通过比较不同周期的移动平均线来判断价格趋势。
        
        Args:
            closes (list): 收盘价序列
            short_period (int): 短期周期，默认为10
            long_period (int): 长期周期，默认为20
            
        Returns:
            dict: 包含价格趋势分析结果的字典
        """
        logging.debug(f"分析价格趋势，短期周期: {short_period}，长期周期: {long_period}，数据点数: {len(closes)}")
        if len(closes) < long_period:
            logging.warning("数据不足，无法进行价格趋势分析")
            return {'trend': 'neutral', 'strength': 0, 'details': '数据不足'}

        short_ma = sum(closes[-short_period:]) / short_period
        long_ma = sum(closes[-long_period:]) / long_period
        current_price = closes[-1]

        # 趋势判断
        if current_price > short_ma > long_ma:
            trend = 'up'
            strength = min(1.0, (current_price - long_ma) / long_ma * 10)
            logging.debug("价格呈上升趋势")
        elif current_price < short_ma < long_ma:
            trend = 'down'
            strength = min(1.0, (long_ma - current_price) / long_ma * 10)
            logging.debug("价格呈下降趋势")
        else:
            trend = 'neutral'
            strength = 0.5
            logging.debug("价格呈震荡趋势")

        result = {
            'trend': trend,
            'strength': strength,
            'details': f'价格趋势: {trend}, 短期MA: {short_ma:.2f}, 长期MA: {long_ma:.2f}'
        }
        logging.debug(f"价格趋势分析完成: {result['details']}")
        return result

    @staticmethod
    def analyze_volume(volumes):
        """分析成交量趋势
        
        通过分析成交量变化来判断市场活跃度。
        
        Args:
            volumes (list): 成交量序列
            
        Returns:
            dict: 包含成交量分析结果的字典
        """
        logging.debug(f"分析成交量趋势，数据点数: {len(volumes)}")
        if len(volumes) < 10:
            logging.warning("成交量数据不足，无法进行分析")
            return {'trend': 'neutral', 'details': '数据不足'}

        # 计算最近5期和之前5期的平均成交量
        recent_volume = sum(volumes[-5:]) / 5
        previous_volume = sum(volumes[-10:-5]) / 5

        # 判断成交量趋势
        if recent_volume > previous_volume * 1.1:  # 成交量增加超过10%
            trend = 'increasing'
            details = f'成交量增加，当前: {recent_volume:.2f}, 之前: {previous_volume:.2f}'
            logging.debug("成交量呈上升趋势")
        elif recent_volume < previous_volume * 0.9:  # 成交量减少超过10%
            trend = 'decreasing'
            details = f'成交量减少，当前: {recent_volume:.2f}, 之前: {previous_volume:.2f}'
            logging.debug("成交量呈下降趋势")
        else:
            trend = 'stable'
            details = f'成交量稳定，当前: {recent_volume:.2f}, 之前: {previous_volume:.2f}'
            logging.debug("成交量保持稳定")

        result = {
            'trend': trend,
            'details': details
        }
        logging.debug(f"成交量分析完成: {result['details']}")
        return result

    @staticmethod
    def perform_technical_analysis(market_data):
        """执行完整的技术分析
        
        整合所有技术指标分析，生成全面的技术分析报告。
        
        Args:
            market_data (dict): 市场数据字典，包含价格、成交量等信息
            
        Returns:
            dict: 包含所有技术分析结果的字典
        """
        logging.info("开始执行完整的技术分析")
        closes = market_data.get('closes', [])
        volumes = market_data.get('volumes', [])
        technicals = market_data.get('technicals', {})
        
        if not closes or not volumes:
            logging.warning("缺少必要的市场数据，无法执行技术分析")
            return {}
            
        # 获取技术指标
        rsi_value = technicals.get('rsi', 50)
        rsi_analysis = TechnicalAnalyzer.analyze_rsi(rsi_value)
        logging.debug(f"RSI分析完成: {rsi_analysis['details']}")
        
        macd_analysis, macd_line, macd_signal, macd_histogram = TechnicalAnalyzer.analyze_macd(closes)
        logging.debug(f"MACD分析完成: {macd_analysis['details']}")
        
        price_trend = TechnicalAnalyzer.analyze_price_trend(closes)
        logging.debug(f"价格趋势分析完成: {price_trend['details']}")
        
        volume_analysis = TechnicalAnalyzer.analyze_volume(volumes)
        logging.debug(f"成交量分析完成: {volume_analysis['details']}")
        
        # 计算信号计数
        bullish_signals = 0
        bearish_signals = 0

        if rsi_analysis['condition'] == 'oversold':
            bullish_signals += 1
            logging.debug("检测到RSI超卖看涨信号")
        elif rsi_analysis['condition'] == 'overbought':
            bearish_signals += 1
            logging.debug("检测到RSI超买看跌信号")

        if macd_analysis['crossover'] == 'golden':
            bullish_signals += 1
            logging.debug("检测到MACD金叉看涨信号")
        elif macd_analysis['crossover'] == 'death':
            bearish_signals += 1
            logging.debug("检测到MACD死叉看跌信号")

        if price_trend['trend'] == 'up':
            bullish_signals += 1
            logging.debug("检测到价格上升趋势信号")
        elif price_trend['trend'] == 'down':
            bearish_signals += 1
            logging.debug("检测到价格下降趋势信号")

        if volume_analysis['trend'] == 'increasing':
            bullish_signals += 1
            logging.debug("检测到成交量上升信号")

        total_signals = max(bullish_signals + bearish_signals, 1)
        overall_strength = abs(bullish_signals - bearish_signals) / total_signals

        result = {
            'rsi': rsi_analysis,
            'macd': macd_analysis,
            'price_trend': price_trend,
            'volume': volume_analysis,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'overall_strength': overall_strength,
            'signal_bias': 'bullish' if bullish_signals > bearish_signals else 'bearish' if bearish_signals > bullish_signals else 'neutral'
        }
        
        logging.info(f"技术分析完成 - 看涨信号: {bullish_signals}, 看跌信号: {bearish_signals}, 总体偏向: {result['signal_bias']}")
        return result