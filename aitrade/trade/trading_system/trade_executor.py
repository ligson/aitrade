import logging

import ccxt
import json
from datetime import datetime
from typing import Dict, Any


class TradeExecutor:
    """交易执行器
    
    负责执行交易订单，管理持仓和交易日志。
    支持多种交易所和代理设置。
    
    Attributes:
        exchange: CCXT交易所实例
        position: 当前持仓信息
        trade_log: 交易日志列表
    """

    def __init__(self, exchange_type: str, api_key: str, secret: str, sandbox: bool = True,
                 proxies: Dict[str, str] = None):
        """
        初始化交易执行器

        Args:
            exchange_type (str): 交易所类型 ('binance', 'okx')
            api_key (str): API密钥
            secret (str): API密钥
            sandbox (bool): 是否使用沙盒模式，默认为True
            proxies (Dict[str, str], optional): 代理设置
            
        Example:
            >>> executor = TradeExecutor('binance', 'your_api_key', 'your_secret', True)
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
            logging.info(f"初始化Binance交易所用于交易执行，沙盒模式: {sandbox}")
        else:
            self.exchange = ccxt.okx(ccxt_cfg)
            logging.info(f"初始化OKX交易所用于交易执行，沙盒模式: {sandbox}")

        # 初始化持仓和交易日志
        self.position = None
        self.trade_log = []
        logging.debug("交易执行器初始化完成")

    def execute_trade_with_risk_management(self, symbol: str, signal: Dict[str, Any], data: Dict[str, Any],
                                           risk_manager) -> None:
        """
        带风险管理的交易执行
        
        根据交易信号和市场数据执行交易，并应用风险管理规则。
        这是交易执行的核心方法，整合了信号分析、风险管理和订单执行。

        Args:
            symbol (str): 交易对，例如 'BTC/USDT'
            signal (Dict[str, Any]): 交易信号，包含操作建议和置信度等信息
            data (Dict[str, Any]): 市场数据，包含价格和各种技术指标
            risk_manager: 风险管理器实例
            
        Example:
            >>> market_data = fetcher.get_enhanced_market_data()
            >>> signal = generator.get_ai_signal(market_data)
            >>> executor.execute_trade_with_risk_management('BTC/USDT', signal, market_data, risk_manager)
        """
        logging.info(f"开始执行交易 - 信号: {signal['action']}, 置信度: {signal.get('confidence', 0):.2f}")
        
        # 进行风险检查
        if not risk_manager.risk_management_check(data, signal['action']):
            logging.warning("风控检查未通过，取消交易")
            return

        try:
            # 获取账户余额
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total']['USDT']
            
            logging.info(f"账户USDT余额: {usdt_balance}")

            # 买入操作
            if signal['action'] == 'buy' and usdt_balance > 10:
                # 计算交易数量
                amount = risk_manager.calculate_position_size(
                    usdt_balance,
                    risk_per_trade=0.02,
                    stop_loss_pct=signal.get('stop_loss_pct', 0.05)
                ) / data['price']
                
                logging.info(f"计算交易数量: {amount}")

                # 加载市场信息以获取最小交易量限制
                markets = self.exchange.load_markets()
                market = markets[symbol]
                min_amount = market['limits']['amount']['min']
                # 确保交易数量不低于最小限制
                amount = max(amount, min_amount)
                
                logging.info(f"调整后交易数量: {amount} (最小: {min_amount})")

                # 创建市价买单
                order = self.exchange.create_order(
                    symbol, 'market', 'buy', amount
                )
                # 更新持仓信息
                self.position = {
                    'entry_price': data['price'],
                    'stop_loss': data['price'] * (1 - signal['stop_loss_pct']),
                    'amount': amount
                }
                # 记录交易日志
                self._log_trade(signal, order, 'BUY_EXECUTED')
                logging.info(f"买单执行成功 - 价格: {data['price']}, 数量: {amount}")

            # 卖出操作
            elif signal['action'] == 'sell' and self.position:
                # 创建市价卖单
                order = self.exchange.create_order(
                    symbol, 'market', 'sell', self.position['amount']
                )
                # 记录交易日志
                self._log_trade(signal, order, 'SELL_EXECUTED')
                # 清空持仓
                self.position = None
                logging.info(f"卖单执行成功 - 价格: {data['price']}, 数量: {self.position['amount']}")
            else:
                logging.info("不满足交易条件，跳过交易执行")

        except Exception as e:
            logging.error(f"交易执行错误: {e}")
            raise

    def _log_trade(self, signal: Dict[str, Any], order: Dict[str, Any], action: str) -> None:
        """
        交易日志
        
        记录交易执行的详细信息到日志和交易日志列表。

        Args:
            signal (Dict[str, Any]): 交易信号
            order (Dict[str, Any]): 订单信息
            action (str): 操作类型
        """
        # 构建日志条目
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'signal': signal,
            'order_id': order['id'],
            'price': order['price'],
            'amount': order['amount']
        }
        # 添加到交易日志列表
        self.trade_log.append(log_entry)
        # 输出到日志
        logging.info(f"交易日志: {json.dumps(log_entry, indent=2, ensure_ascii=False)}")

    def get_position(self) -> Dict[str, Any]:
        """
        获取当前持仓
        
        Returns:
            Dict[str, Any]: 当前持仓信息，如果没有持仓则返回None
            
        Example:
            >>> position = executor.get_position()
            >>> if position: print(f"当前持仓: {position}")
        """
        logging.debug(f"获取当前持仓: {self.position}")
        return self.position

    def set_position(self, position: Dict[str, Any]) -> None:
        """
        设置持仓
        
        Args:
            position (Dict[str, Any]): 持仓信息
            
        Example:
            >>> executor.set_position({'entry_price': 50000, 'stop_loss': 49000, 'amount': 0.1})
        """
        self.position = position
        logging.info(f"持仓已更新: {position}")