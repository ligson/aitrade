import json
import logging
from datetime import datetime
from typing import Any, Dict

import ccxt


class TradeExecutor:
    """交易执行器。"""

    def __init__(self, exchange_type: str, api_key: str, secret: str, password: str = '', sandbox: bool = True, proxies: Dict[str, str] = None):
        ccxt_cfg = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        }

        if exchange_type == "okx" and password:
            ccxt_cfg['password'] = password

        if proxies:
            ccxt_cfg['proxies'] = proxies

        if exchange_type == "binance":
            ccxt_cfg['options'] = {
                'defaultType': 'spot',
                'fetchMarkets': {
                    'types': ['spot'],
                },
            }
            self.exchange = ccxt.binance(ccxt_cfg)
            logging.info("初始化Binance交易所用于交易执行，沙盒模式: %s", sandbox)
        else:
            self.exchange = ccxt.okx(ccxt_cfg)
            logging.info("初始化OKX交易所用于交易执行，沙盒模式: %s", sandbox)

        if sandbox and hasattr(self.exchange, 'set_sandbox_mode'):
            self.exchange.set_sandbox_mode(True)

        self.position = None
        self.trade_log = []
        self.trade_logger = logging.getLogger('trade')
        logging.debug("交易执行器初始化完成")

    def execute_trade_with_risk_management(self, symbol: str, signal: Dict[str, Any], data: Dict[str, Any], risk_manager) -> None:
        logging.info("开始执行交易 - 信号: %s, 置信度: %.2f, 策略: %s", signal['action'], signal.get('confidence', 0), signal.get('strategy', 'unknown'))

        if not risk_manager.risk_management_check(data, signal):
            logging.warning("风控检查未通过，取消交易")
            return

        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0)
            logging.info("账户USDT余额: %s", usdt_balance)

            if signal['action'] == 'buy' and usdt_balance > 10:
                stop_loss_pct = self._resolve_stop_loss_pct(signal, data)
                amount = risk_manager.calculate_position_size(
                    usdt_balance,
                    risk_per_trade=signal.get('risk_per_trade', 0.02),
                    stop_loss_pct=stop_loss_pct,
                ) / data['price']
                logging.info("计算交易数量: %s", amount)

                markets = self.exchange.load_markets()
                if symbol not in markets:
                    logging.error("交易对 %s 不在交易所市场列表中", symbol)
                    available_symbols = list(markets.keys())
                    if available_symbols:
                        logging.debug("部分可用交易对示例: %s", available_symbols[:10])
                    return

                market = markets[symbol]
                min_amount = market['limits']['amount']['min'] if 'min' in market['limits']['amount'] else 0
                amount = max(amount, min_amount)
                logging.info("调整后交易数量: %s (最小: %s)", amount, min_amount)

                order = self.exchange.create_order(symbol, 'market', 'buy', amount)
                stop_loss_price = signal.get('stop_loss_price', data['price'] * (1 - stop_loss_pct))
                trailing_stop_price = signal.get('trailing_stop_price')
                self.position = {
                    'entry_price': data['price'],
                    'stop_loss': stop_loss_price,
                    'initial_stop_loss': stop_loss_price,
                    'trailing_stop_price': trailing_stop_price,
                    'highest_price': data['price'],
                    'highest_close': data['price'],
                    'amount': amount,
                    'strategy': signal.get('strategy'),
                    'meta': signal.get('meta', {}),
                }
                self._log_trade(signal, order, 'BUY_EXECUTED')
                logging.info("买单执行成功 - 价格: %s, 数量: %s", data['price'], amount)

            elif signal['action'] == 'sell' and self.position:
                position_amount = self.position['amount']
                order = self.exchange.create_order(symbol, 'market', 'sell', position_amount)
                self._log_trade(signal, order, 'SELL_EXECUTED')
                self.position = None
                logging.info("卖单执行成功 - 价格: %s, 数量: %s", data['price'], position_amount)
            else:
                logging.info("不满足交易条件，跳过交易执行")

        except Exception as e:
            logging.error("交易执行错误: %s", e)
            raise

    def update_position_risk(self, stop_loss=None, trailing_stop_price=None, market_price=None, meta=None) -> None:
        if not self.position:
            return

        if market_price is not None:
            self.position['highest_price'] = max(self.position.get('highest_price', market_price), market_price)
            self.position['highest_close'] = max(self.position.get('highest_close', market_price), market_price)

        if stop_loss is not None:
            current_stop_loss = self.position.get('stop_loss')
            if current_stop_loss is None or stop_loss > current_stop_loss:
                self.position['stop_loss'] = stop_loss

        if trailing_stop_price is not None:
            self.position['trailing_stop_price'] = trailing_stop_price

        if meta:
            merged_meta = dict(self.position.get('meta', {}))
            merged_meta.update(meta)
            self.position['meta'] = merged_meta

        logging.info("持仓风控信息已更新: %s", self.position)

    def _resolve_stop_loss_pct(self, signal: Dict[str, Any], data: Dict[str, Any]) -> float:
        if signal.get('stop_loss_price') is not None:
            stop_loss_price = signal['stop_loss_price']
            return max((data['price'] - stop_loss_price) / data['price'], 1e-6)
        return max(signal.get('stop_loss_pct', 0.05), 1e-6)

    def _log_trade(self, signal: Dict[str, Any], order: Dict[str, Any], action: str) -> None:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'signal': signal,
            'order_id': order.get('id', 'unknown'),
            'price': order.get('price', 'unknown'),
            'amount': order.get('amount', 'unknown'),
        }
        self.trade_log.append(log_entry)
        logging.info("交易日志: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))
        self.trade_logger.info("交易成功: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))

    def get_position(self) -> Dict[str, Any]:
        logging.debug("获取当前持仓: %s", self.position)
        return self.position

    def set_position(self, position: Dict[str, Any]) -> None:
        self.position = position
        logging.info("持仓已更新: %s", position)
