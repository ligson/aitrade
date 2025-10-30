import numpy as np
from typing import Dict, Any


class RiskManager:
    """风险管理器"""

    @staticmethod
    def risk_management_check(data: Dict[str, Any], proposed_action: str) -> bool:
        """
        风险管理检查
        
        Args:
            data: 市场数据
            proposed_action: 建议的操作
            
        Returns:
            是否通过风险检查
        """
        if proposed_action == 'hold':
            return True

        price = data['price']
        rsi = data['technicals']['rsi']
        volatility = np.std(data['closes'][-10:]) / np.mean(data['closes'][-10:])

        # 避免在极端波动时交易
        if volatility > 0.05:
            return False

        # 避免在RSI极端值时反向操作
        if proposed_action == 'buy' and rsi > 80:
            return False
        if proposed_action == 'sell' and rsi < 20:
            return False

        return True

    @staticmethod
    def calculate_position_size(balance: float, risk_per_trade: float = 0.02, stop_loss_pct: float = 0.05) -> float:
        """
        根据账户余额和风险承受能力计算仓位大小
        
        Args:
            balance: 账户余额
            risk_per_trade: 每笔交易风险比例
            stop_loss_pct: 止损百分比
            
        Returns:
            仓位大小
        """
        risk_amount = balance * risk_per_trade
        position_size = risk_amount / stop_loss_pct
        return min(position_size, balance * 0.1)  # 单次交易不超过总资金的10%

    @staticmethod
    def check_market_conditions(volumes: list, volatility_threshold: float = 0.03) -> bool:
        """
        检查市场条件
        
        Args:
            volumes: 成交量数据
            volatility_threshold: 波动率阈值
            
        Returns:
            市场条件是否合适
        """
        if len(volumes) < 10:
            return True  # 数据不足时默认条件合适

        recent_volatility = np.std(volumes[-10:]) / np.mean(volumes[-10:])
        return recent_volatility < volatility_threshold