import logging
import numpy as np
from typing import Dict, Any


class RiskManager:
    """风险管理器
    
    负责交易风险控制，包括风险检查、仓位计算和市场条件评估。
    通过多种风险控制机制，确保交易在可接受的风险范围内进行。
    """

    @staticmethod
    def risk_management_check(data: Dict[str, Any], proposed_action: str) -> bool:
        """
        风险管理检查
        
        检查当前市场条件是否适合执行交易操作，避免在高风险情况下交易。
        主要检查包括波动率过高和RSI极端值等情况。
        
        Args:
            data (Dict[str, Any]): 市场数据，包含价格和技术指标等信息
            proposed_action (str): 建议的操作 ('buy', 'sell', 'hold')
            
        Returns:
            bool: 是否通过风险检查，True表示可以交易，False表示应该避免交易
            
        Example:
            >>> market_data = fetcher.get_enhanced_market_data()
            >>> can_trade = RiskManager.risk_management_check(market_data, 'buy')
            >>> if can_trade: print("风险检查通过，可以交易")
        """
        # 如果是持有操作，则无需风险检查
        if proposed_action == 'hold':
            logging.debug("操作为持有，无需风险检查")
            return True

        # 获取当前价格和RSI指标
        price = data['price']
        rsi = data['technicals']['rsi']
        
        # 计算最近10个周期的价格波动率
        closes = data['closes']
        volatility = np.std(closes[-10:]) / np.mean(closes[-10:])
        
        logging.info(f"风险检查 - 价格: {price}, RSI: {rsi:.2f}, 波动率: {volatility:.4f}")

        # 避免在极端波动时交易
        # 当波动率超过5%时，认为市场过于不稳定，应避免交易
        if volatility > 0.05:
            logging.warning(f"市场波动率过高 ({volatility:.4f})，取消交易")
            return False

        # 避免在RSI极端值时反向操作
        # RSI > 80 表示超买，应避免继续买入
        if proposed_action == 'buy' and rsi > 80:
            logging.warning(f"RSI值过高 ({rsi:.2f})，避免买入")
            return False
        # RSI < 20 表示超卖，应避免继续卖出
        if proposed_action == 'sell' and rsi < 20:
            logging.warning(f"RSI值过低 ({rsi:.2f})，避免卖出")
            return False

        logging.info("风险检查通过，可以执行交易")
        return True

    @staticmethod
    def calculate_position_size(balance: float, risk_per_trade: float = 0.02, stop_loss_pct: float = 0.05) -> float:
        """
        根据账户余额和风险承受能力计算仓位大小
        
        使用固定比例风险管理方法，确保单笔交易风险控制在账户余额的一定比例内。
        这是一种经典的仓位管理方法，有助于在长期交易中保护资本。
        
        Args:
            balance (float): 账户余额
            risk_per_trade (float): 每笔交易风险比例，默认0.02 (2%)
            stop_loss_pct (float): 止损百分比，默认0.05 (5%)
            
        Returns:
            float: 仓位大小（以基础货币计价）
            
        Example:
            >>> position_size = RiskManager.calculate_position_size(10000, 0.02, 0.05)
            >>> print(f"建议仓位大小: {position_size}")
        """
        # 计算可承受的风险金额 - 账户余额的2%
        risk_amount = balance * risk_per_trade
        logging.debug(f"可承受风险金额: {risk_amount:.2f} (账户余额的{risk_per_trade*100:.0f}%)")
        
        # 根据止损百分比计算仓位大小
        # 公式: 仓位大小 = 风险金额 / 止损百分比
        position_size = risk_amount / stop_loss_pct
        logging.debug(f"根据止损计算的仓位大小: {position_size:.2f}")
        
        # 限制单次交易不超过总资金的10%
        # 这是为了防止单笔交易占用过多资金
        max_position = balance * 0.1
        final_position = min(position_size, max_position)
        logging.debug(f"最大允许仓位: {max_position:.2f}, 实际仓位: {final_position:.2f}")
        
        logging.info(f"计算仓位完成 - 账户余额: {balance}, 仓位大小: {final_position:.2f}")
        
        return final_position

    @staticmethod
    def check_market_conditions(volumes: list, volatility_threshold: float = 0.03) -> bool:
        """
        检查市场条件
        
        评估市场活跃度，避免在流动性不足或过于平静的市场中交易。
        通过分析成交量的波动性来判断市场活跃程度。
        
        Args:
            volumes (list): 成交量数据列表
            volatility_threshold (float): 波动率阈值，默认0.03
            
        Returns:
            bool: 市场条件是否合适，True表示合适，False表示不合适
            
        Example:
            >>> market_data = fetcher.get_enhanced_market_data()
            >>> is_suitable = RiskManager.check_market_conditions(market_data['volumes'])
            >>> if is_suitable: print("市场条件良好，适合交易")
        """
        # 如果数据不足10个点，则默认条件合适
        if len(volumes) < 10:
            logging.debug("成交量数据不足，市场条件默认为合适")
            return True

        # 计算最近10个周期成交量的波动率
        recent_volatility = np.std(volumes[-10:]) / np.mean(volumes[-10:])
        # 判断波动率是否低于阈值
        is_suitable = recent_volatility < volatility_threshold
        
        logging.info(f"市场条件检查 - 近期波动率: {recent_volatility:.4f}, 是否合适: {is_suitable}")
        
        # 如果波动率过低，说明市场过于平静，可能不适合交易
        if not is_suitable:
            logging.warning(f"市场波动率过低 ({recent_volatility:.4f})，可能不适合交易")
        
        return is_suitable