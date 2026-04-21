import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import ccxt

from .sqlite_trade_store import SQLiteTradeStore


class TradeExecutor:
    """交易执行器。"""

    def __init__(
        self,
        exchange_type: str,
        api_key: str,
        secret: str,
        password: str = '',
        sandbox: bool = True,
        proxies: Dict[str, str] = None,
        persistence_config: Optional[Dict[str, Any]] = None,
    ):
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

        self.exchange_type = exchange_type
        self.sandbox = sandbox
        self.position = None
        self.trade_log = []
        self.trade_logger = logging.getLogger('trade')
        self.persistence_config = persistence_config or {}
        self.persistence_enabled = bool(self.persistence_config.get('enabled', True))
        self.persist_position = bool(self.persistence_config.get('persist_position', True))
        self.store = None
        if self.persistence_enabled:
            self.store = SQLiteTradeStore(self.persistence_config['sqlite_path'])
            logging.info("SQLite交易记录已启用: %s", self.store.db_path)
        logging.debug("交易执行器初始化完成")

    def close(self) -> None:
        if self.store is not None:
            self.store.close()
            logging.info("SQLite交易记录已关闭")

    def restore_position_from_storage(self, symbol: str) -> Optional[Dict[str, Any]]:
        if self.store is None or not self.persist_position:
            return None

        stored_position = self.store.get_position_state(symbol)
        if stored_position is None:
            logging.info("未找到可恢复的本地持仓: %s", symbol)
            return None

        self.position = {
            'entry_time': stored_position.get('entry_time'),
            'entry_price': stored_position.get('entry_price'),
            'stop_loss': stored_position.get('stop_loss'),
            'initial_stop_loss': stored_position.get('initial_stop_loss'),
            'trailing_stop_price': stored_position.get('trailing_stop_price'),
            'highest_price': stored_position.get('highest_price'),
            'highest_close': stored_position.get('highest_close'),
            'amount': stored_position.get('amount'),
            'strategy': stored_position.get('strategy'),
            'meta': stored_position.get('meta', {}),
        }
        logging.info("已从SQLite恢复本地持仓: %s", self.position)
        return self.position

    def execute_trade_with_risk_management(
        self,
        symbol: str,
        signal: Dict[str, Any],
        data: Dict[str, Any],
        risk_manager,
        trigger_source: str = 'strategy_signal',
    ) -> None:
        logging.info("开始执行交易 - 信号: %s, 置信度: %.2f, 策略: %s", signal['action'], signal.get('confidence', 0), signal.get('strategy', 'unknown'))

        position_before = self._snapshot_position(self.position)
        risk_check = risk_manager.risk_management_check(data, signal)
        if not risk_check['passed']:
            logging.warning("风控检查未通过，取消交易: %s", risk_check['reason'])
            self._persist_trade_record(
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='risk_rejected',
                result_reason=risk_check['reason'],
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=position_before,
            )
            return

        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0)
            logging.info("账户USDT余额: %s", usdt_balance)

            if signal['action'] == 'buy' and usdt_balance <= 10:
                reason = 'USDT余额不足，跳过买入'
                logging.info(reason)
                self._persist_trade_record(
                    signal=signal,
                    data=data,
                    trigger_source=trigger_source,
                    result='skipped',
                    result_reason=reason,
                    risk_snapshot=risk_check['metrics'],
                    position_before=position_before,
                    position_after=position_before,
                )
                return

            if signal['action'] == 'buy':
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
                    self._persist_trade_record(
                        signal=signal,
                        data=data,
                        trigger_source=trigger_source,
                        result='skipped',
                        result_reason=f'交易对 {symbol} 不在交易所市场列表中',
                        requested_amount=amount,
                        risk_snapshot=risk_check['metrics'],
                        position_before=position_before,
                        position_after=position_before,
                    )
                    return

                market = markets[symbol]
                min_amount = market['limits']['amount']['min'] if 'min' in market['limits']['amount'] else 0
                amount = max(amount, min_amount)
                logging.info("调整后交易数量: %s (最小: %s)", amount, min_amount)

                order = self.exchange.create_order(symbol, 'market', 'buy', amount)
                stop_loss_price = signal.get('stop_loss_price', data['price'] * (1 - stop_loss_pct))
                trailing_stop_price = signal.get('trailing_stop_price')
                self.position = {
                    'entry_time': self._utc_now(),
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
                trade_id = self._persist_trade_record(
                    signal=signal,
                    data=data,
                    trigger_source=trigger_source,
                    result='executed',
                    result_reason='买单执行成功',
                    requested_amount=amount,
                    risk_snapshot=risk_check['metrics'],
                    position_before=position_before,
                    position_after=self._snapshot_position(self.position),
                    order=order,
                )
                self._persist_position_state(symbol, self.position, trade_id)
                self._log_trade(signal, order, 'BUY_EXECUTED')
                logging.info("买单执行成功 - 价格: %s, 数量: %s", data['price'], amount)
                return

            if signal['action'] == 'sell' and self.position:
                position_amount = self.position['amount']
                order = self.exchange.create_order(symbol, 'market', 'sell', position_amount)
                trade_id = self._persist_trade_record(
                    signal=signal,
                    data=data,
                    trigger_source=trigger_source,
                    result='executed',
                    result_reason='卖单执行成功',
                    requested_amount=position_amount,
                    risk_snapshot=risk_check['metrics'],
                    position_before=position_before,
                    position_after=None,
                    order=order,
                )
                self._log_trade(signal, order, 'SELL_EXECUTED')
                self.position = None
                self._delete_position_state(symbol)
                logging.info("卖单执行成功 - 价格: %s, 数量: %s, 记录ID: %s", data['price'], position_amount, trade_id)
                return

            reason = '不满足交易条件，跳过交易执行'
            logging.info(reason)
            self._persist_trade_record(
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='skipped',
                result_reason='当前无持仓可卖' if signal['action'] == 'sell' else reason,
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=position_before,
            )

        except Exception as e:
            logging.error("交易执行错误: %s", e)
            self._persist_trade_record(
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='failed',
                result_reason='交易执行异常',
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=self._snapshot_position(self.position),
                error_message=str(e),
            )
            raise

    def update_position_risk(self, symbol: str, stop_loss=None, trailing_stop_price=None, market_price=None, meta=None) -> None:
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

        self._persist_position_state(symbol, self.position)
        logging.info("持仓风控信息已更新: %s", self.position)

    def _resolve_stop_loss_pct(self, signal: Dict[str, Any], data: Dict[str, Any]) -> float:
        if signal.get('stop_loss_price') is not None:
            stop_loss_price = signal['stop_loss_price']
            return max((data['price'] - stop_loss_price) / data['price'], 1e-6)
        return max(signal.get('stop_loss_pct', 0.05), 1e-6)

    def _log_trade(self, signal: Dict[str, Any], order: Dict[str, Any], action: str) -> None:
        log_entry = {
            'timestamp': self._utc_now(),
            'action': action,
            'signal': signal,
            'order_id': order.get('id', 'unknown'),
            'price': order.get('price', 'unknown'),
            'amount': order.get('amount', 'unknown'),
        }
        self.trade_log.append(log_entry)
        logging.info("交易日志: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))
        self.trade_logger.info("交易成功: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))

    def _persist_trade_record(
        self,
        signal: Dict[str, Any],
        data: Dict[str, Any],
        trigger_source: str,
        result: str,
        result_reason: str,
        risk_snapshot: Optional[Dict[str, Any]],
        position_before: Optional[Dict[str, Any]],
        position_after: Optional[Dict[str, Any]],
        requested_amount: Optional[float] = None,
        order: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        if self.store is None:
            return None

        record = {
            'created_at': self._utc_now(),
            'symbol': data.get('symbol'),
            'strategy': signal.get('strategy', 'unknown'),
            'trigger_source': trigger_source,
            'side': signal.get('action', 'unknown'),
            'signal_confidence': signal.get('confidence'),
            'signal_reason': signal.get('reason'),
            'market_price': data.get('price'),
            'requested_amount': requested_amount,
            'stop_loss_price': signal.get('stop_loss_price'),
            'trailing_stop_price': signal.get('trailing_stop_price'),
            'risk_per_trade': signal.get('risk_per_trade'),
            'exchange_type': self.exchange_type,
            'sandbox': self.sandbox,
            'result': result,
            'result_reason': result_reason,
            'error_message': error_message,
            'signal_meta': signal.get('meta', {}),
            'risk_snapshot': risk_snapshot,
            'position_before': position_before,
            'position_after': position_after,
            'order_raw': order,
        }

        if order is not None:
            record.update({
                'order_id': order.get('id'),
                'order_status': order.get('status'),
                'order_type': order.get('type'),
                'order_price': order.get('price'),
                'order_amount': order.get('amount'),
                'order_cost': order.get('cost'),
            })

        return self.store.insert_trade_record(record)

    def _persist_position_state(self, symbol: str, position: Optional[Dict[str, Any]], source_trade_id: Optional[int] = None) -> None:
        if self.store is None or not self.persist_position or position is None:
            return
        self.store.upsert_position_state(symbol, position, source_trade_id)

    def _delete_position_state(self, symbol: str) -> None:
        if self.store is None or not self.persist_position:
            return
        self.store.delete_position_state(symbol)

    @staticmethod
    def _snapshot_position(position: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if position is None:
            return None
        return json.loads(json.dumps(position, ensure_ascii=False))

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_position(self) -> Dict[str, Any]:
        logging.debug("获取当前持仓: %s", self.position)
        return self.position

    def set_position(self, position: Dict[str, Any]) -> None:
        self.position = position
        logging.info("持仓已更新: %s", position)
