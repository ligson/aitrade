import logging
from typing import Any, Dict

import numpy as np


class RiskManager:
    """风险管理器。"""

    @staticmethod
    def risk_management_check(data: Dict[str, Any], signal: Dict[str, Any]) -> bool:
        proposed_action = signal.get('action', 'hold')
        strategy = signal.get('strategy', 'unknown')

        if proposed_action == 'hold':
            logging.debug("操作为持有，无需风险检查")
            return True

        if signal.get('force_execution'):
            logging.info("检测到强制执行信号，跳过常规风控拦截")
            return True

        closes = data.get('closes', [])
        if len(closes) < 10:
            logging.warning("价格数据不足，取消交易")
            return False

        price = data['price']
        rsi = data['technicals']['rsi']
        volatility = np.std(closes[-10:]) / max(np.mean(closes[-10:]), 1e-10)
        logging.info("风险检查 - 策略: %s, 价格: %s, RSI: %.2f, 波动率: %.4f", strategy, price, rsi, volatility)

        if volatility > 0.05:
            logging.warning("市场波动率过高 (%.4f)，取消交易", volatility)
            return False

        if strategy == 'btc_spot_breakout':
            stop_loss_price = signal.get('stop_loss_price')
            if proposed_action == 'buy' and stop_loss_price is not None and stop_loss_price >= price:
                logging.warning("规则策略止损价异常，取消买入")
                return False
            logging.info("规则策略风控检查通过")
            return True

        if proposed_action == 'buy' and rsi > 80:
            logging.warning("RSI值过高 (%.2f)，避免买入", rsi)
            return False
        if proposed_action == 'sell' and rsi < 20:
            logging.warning("RSI值过低 (%.2f)，避免卖出", rsi)
            return False

        logging.info("风险检查通过，可以执行交易")
        return True

    @staticmethod
    def calculate_position_size(balance: float, risk_per_trade: float = 0.02, stop_loss_pct: float = 0.05) -> float:
        safe_stop_loss_pct = max(stop_loss_pct, 1e-6)
        risk_amount = balance * risk_per_trade
        logging.debug("可承受风险金额: %.2f (账户余额的%.2f%%)", risk_amount, risk_per_trade * 100)

        position_size = risk_amount / safe_stop_loss_pct
        logging.debug("根据止损计算的仓位大小: %.2f", position_size)

        max_position = balance * 0.1
        final_position = min(position_size, max_position)
        logging.debug("最大允许仓位: %.2f, 实际仓位: %.2f", max_position, final_position)

        logging.info("计算仓位完成 - 账户余额: %s, 仓位大小: %.2f", balance, final_position)
        return final_position

    @staticmethod
    def check_market_conditions(volumes: list, volatility_threshold: float = 0.03) -> bool:
        if len(volumes) < 10:
            logging.debug("成交量数据不足，市场条件默认为合适")
            return True

        recent_volatility = np.std(volumes[-10:]) / max(np.mean(volumes[-10:]), 1e-10)
        is_suitable = recent_volatility < volatility_threshold
        logging.info("市场条件检查 - 近期波动率: %.4f, 是否合适: %s", recent_volatility, is_suitable)

        if not is_suitable:
            logging.warning("市场波动率过低 (%.4f)，可能不适合交易", recent_volatility)

        return is_suitable
