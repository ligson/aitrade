import numpy as np


class MarketAnalyzer:
    """市场环境分析器"""

    @staticmethod
    def assess_market_context(market_data):
        """评估市场整体环境"""
        closes = market_data.get('closes', [])
        volumes = market_data.get('volumes', [])
        current_price = market_data.get('price', 0)
        
        if len(closes) < 20:
            return {'volatility': 'unknown', 'trend': 'unknown', 'details': '数据不足'}

        # 波动率分析
        returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        volatility = np.std(returns) * np.sqrt(365)  # 年化波动率

        volatility_level = 'high' if volatility > 0.8 else 'medium' if volatility > 0.4 else 'low'

        # 趋势强度
        price_change = (current_price - closes[0]) / closes[0]
        trend_strength = 'strong' if abs(price_change) > 0.1 else 'moderate' if abs(price_change) > 0.05 else 'weak'
        trend_direction = 'up' if price_change > 0 else 'down' if price_change < 0 else 'flat'

        return {
            'volatility': volatility_level,
            'trend_strength': trend_strength,
            'trend_direction': trend_direction,
            'price_change_pct': price_change * 100,
            'details': f'市场{trend_direction}趋势{trend_strength}, 波动率{volatility_level}'
        }