import numpy as np
import logging


class MarketAnalyzer:
    """市场环境分析器
    
    负责评估整体市场环境，包括波动率、趋势强度等宏观指标，
    为AI交易信号生成提供市场背景信息。
    """

    @staticmethod
    def assess_market_context(market_data):
        """评估市场整体环境
        
        通过分析价格变化和波动率来评估当前市场环境，
        帮助AI模型更好地理解市场背景。
        
        Args:
            market_data (dict): 市场数据字典，包含价格、成交量等信息
            
        Returns:
            dict: 包含市场环境评估结果的字典
        """
        logging.info("开始评估市场整体环境")
        closes = market_data.get('closes', [])
        volumes = market_data.get('volumes', [])
        current_price = market_data.get('price', 0)
        
        if len(closes) < 20:
            logging.warning("市场数据不足20个点，无法准确评估市场环境")
            return {'volatility': 'unknown', 'trend': 'unknown', 'details': '数据不足'}

        # 波动率分析 - 计算年化波动率
        logging.debug("计算市场波动率")
        returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        volatility = np.std(returns) * np.sqrt(365)  # 年化波动率

        # 根据波动率水平分类市场
        volatility_level = 'high' if volatility > 0.8 else 'medium' if volatility > 0.4 else 'low'
        logging.debug(f"波动率计算完成: {volatility:.4f}，水平: {volatility_level}")

        # 趋势强度分析 - 基于价格变化百分比
        logging.debug("分析市场趋势强度")
        price_change = (current_price - closes[0]) / closes[0]
        trend_strength = 'strong' if abs(price_change) > 0.1 else 'moderate' if abs(price_change) > 0.05 else 'weak'
        trend_direction = 'up' if price_change > 0 else 'down' if price_change < 0 else 'flat'
        logging.debug(f"价格变化: {price_change*100:.2f}%，趋势强度: {trend_strength}，方向: {trend_direction}")

        result = {
            'volatility': volatility_level,
            'trend_strength': trend_strength,
            'trend_direction': trend_direction,
            'price_change_pct': price_change * 100,
            'details': f'市场{trend_direction}趋势{trend_strength}, 波动率{volatility_level}'
        }
        
        logging.info(f"市场环境评估完成: {result['details']}")
        return result