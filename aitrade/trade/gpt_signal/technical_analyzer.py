import numpy as np
import pandas as pd


class TechnicalAnalyzer:
    """技术指标分析器"""

    @staticmethod
    def compute_rsi(prices, period=14):
        """计算RSI指标"""
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

    @staticmethod
    def analyze_rsi(rsi_value):
        """分析RSI指标状态"""
        rsi_analysis = {
            'value': rsi_value,
            'condition': 'neutral',
            'strength': 0,
            'details': ''
        }

        if rsi_value < 30:
            rsi_analysis.update({'condition': 'oversold', 'strength': min(1.0, (30 - rsi_value) / 30)})
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于超卖区域'
        elif rsi_value > 70:
            rsi_analysis.update({'condition': 'overbought', 'strength': min(1.0, (rsi_value - 70) / 30)})
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于超买区域'
        else:
            rsi_analysis['strength'] = 0.5
            rsi_analysis['details'] = f'RSI {rsi_value:.1f} 处于中性区域'

        return rsi_analysis

    @staticmethod
    def analyze_macd(closes):
        """分析MACD指标"""
        # MACD
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
        else:
            macd_analysis['trend'] = 'bearish'
            macd_analysis['momentum'] = min(1.0, abs(float(macd_histogram[-1])) / (abs(float(macd_line[-1])) + 1e-10))

        # 金叉死叉判断
        if macd_line[-1] > signal_line[-1] and macd_histogram[-1] > 0:
            macd_analysis['crossover'] = 'golden'
            macd_analysis['details'] = 'MACD金叉，看涨信号'
        elif macd_line[-1] < signal_line[-1] and macd_histogram[-1] < 0:
            macd_analysis['crossover'] = 'death'
            macd_analysis['details'] = 'MACD死叉，看跌信号'
        else:
            macd_analysis['details'] = 'MACD无明显交叉信号'

        return macd_analysis, macd_line[-1], signal_line[-1], macd_histogram[-1]

    @staticmethod
    def analyze_price_trend(closes, short_period=10, long_period=20):
        """分析价格趋势"""
        if len(closes) < long_period:
            return {'trend': 'neutral', 'strength': 0, 'details': '数据不足'}

        short_ma = sum(closes[-short_period:]) / short_period
        long_ma = sum(closes[-long_period:]) / long_period
        current_price = closes[-1]

        # 趋势判断
        if current_price > short_ma > long_ma:
            trend = 'up'
            strength = min(1.0, (current_price - long_ma) / long_ma * 10)
        elif current_price < short_ma < long_ma:
            trend = 'down'
            strength = min(1.0, (long_ma - current_price) / long_ma * 10)
        else:
            trend = 'neutral'
            strength = 0.5

        return {
            'trend': trend,
            'strength': strength,
            'details': f'价格趋势: {trend}, 短期MA: {short_ma:.2f}, 长期MA: {long_ma:.2f}'
        }

    @staticmethod
    def perform_technical_analysis(market_data):
        """执行完整的技术分析"""
        closes = market_data.get('closes', [])
        volumes = market_data.get('volumes', [])
        technicals = market_data.get('technicals', {})
        
        if not closes or not volumes:
            return {}
            
        # 获取技术指标
        rsi_value = technicals.get('rsi', 50)
        rsi_analysis = TechnicalAnalyzer.analyze_rsi(rsi_value)
        
        macd_analysis, macd_line, macd_signal, macd_histogram = TechnicalAnalyzer.analyze_macd(closes)
        
        price_trend = TechnicalAnalyzer.analyze_price_trend(closes)
        
        volume_analysis = TechnicalAnalyzer.analyze_volume(volumes)
        
        # 计算信号计数
        bullish_signals = 0
        bearish_signals = 0

        if rsi_analysis['condition'] == 'oversold':
            bullish_signals += 1
        elif rsi_analysis['condition'] == 'overbought':
            bearish_signals += 1

        if macd_analysis['crossover'] == 'golden':
            bullish_signals += 1
        elif macd_analysis['crossover'] == 'death':
            bearish_signals += 1

        if price_trend['trend'] == 'up':
            bullish_signals += 1
        elif price_trend['trend'] == 'down':
            bearish_signals += 1

        if volume_analysis['trend'] == 'increasing':
            bullish_signals += 1

        total_signals = max(bullish_signals + bearish_signals, 1)
        overall_strength = abs(bullish_signals - bearish_signals) / total_signals

        return {
            'rsi': rsi_analysis,
            'macd': macd_analysis,
            'price_trend': price_trend,
            'volume': volume_analysis,
            'bullish_signals': bullish_signals,
            'bearish_signals': bearish_signals,
            'overall_strength': overall_strength,
            'signal_bias': 'bullish' if bullish_signals > bearish_signals else 'bearish' if bearish_signals > bullish_signals else 'neutral'
        }