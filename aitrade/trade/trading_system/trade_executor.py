import ccxt
import json
from datetime import datetime
from typing import Dict, Any


class TradeExecutor:
    """交易执行器"""

    def __init__(self, exchange_type: str, api_key: str, secret: str, sandbox: bool = True, proxies: Dict[str, str] = None):
        """
        初始化交易执行器
        
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

        self.position = None
        self.trade_log = []

    def execute_trade_with_risk_management(self, symbol: str, signal: Dict[str, Any], data: Dict[str, Any], risk_manager) -> None:
        """
        带风险管理的交易执行
        
        Args:
            symbol: 交易对
            signal: 交易信号
            data: 市场数据
            risk_manager: 风险管理器实例
        """
        if not risk_manager.risk_management_check(data, signal['action']):
            print("风控检查未通过，取消交易")
            return

        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total']['USDT']

            if signal['action'] == 'buy' and usdt_balance > 10:
                amount = risk_manager.calculate_position_size(
                    usdt_balance,
                    risk_per_trade=0.02,
                    stop_loss_pct=signal.get('stop_loss_pct', 0.05)
                ) / data['price']

                # 最小交易量检查
                markets = self.exchange.load_markets()
                market = markets[symbol]
                amount = max(amount, market['limits']['amount']['min'])

                order = self.exchange.create_order(
                    symbol, 'market', 'buy', amount
                )
                self.position = {
                    'entry_price': data['price'],
                    'stop_loss': data['price'] * (1 - signal['stop_loss_pct']),
                    'amount': amount
                }
                self._log_trade(signal, order, 'BUY_EXECUTED')

            elif signal['action'] == 'sell' and self.position:
                # 简化卖出逻辑
                order = self.exchange.create_order(
                    symbol, 'market', 'sell', self.position['amount']
                )
                self._log_trade(signal, order, 'SELL_EXECUTED')
                self.position = None

        except Exception as e:
            print(f"交易执行错误: {e}")

    def _log_trade(self, signal: Dict[str, Any], order: Dict[str, Any], action: str) -> None:
        """
        交易日志
        
        Args:
            signal: 交易信号
            order: 订单信息
            action: 操作类型
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'signal': signal,
            'order_id': order['id'],
            'price': order['price'],
            'amount': order['amount']
        }
        self.trade_log.append(log_entry)
        print(f"交易日志: {json.dumps(log_entry, indent=2, ensure_ascii=False)}")

    def get_position(self) -> Dict[str, Any]:
        """
        获取当前持仓
        
        Returns:
            当前持仓信息
        """
        return self.position

    def set_position(self, position: Dict[str, Any]) -> None:
        """
        设置持仓
        
        Args:
            position: 持仓信息
        """
        self.position = position