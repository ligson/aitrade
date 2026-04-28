import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import ccxt

from ...config.config_file import DEFAULT_PAPER_BALANCE
from ...config.config_file import TRADE_MODES
from .trade_store_factory import create_trade_store
from .trade_store_factory import summarize_database_target


class TradingHaltError(RuntimeError):
    def __init__(self, reason: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


class TradeExecutor:
    """交易执行器。"""

    def __init__(
        self,
        exchange_type: str,
        api_key: str,
        secret: str,
        password: str = '',
        sandbox: bool = True,
        trade_mode: str = 'sandbox',
        proxies: Dict[str, str] = None,
        persistence_config: Optional[Dict[str, Any]] = None,
        paper_balance: Optional[float] = None,
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

        if trade_mode not in TRADE_MODES:
            raise ValueError(f'不支持的交易方式: {trade_mode}')

        self.exchange_type = exchange_type
        self.sandbox = sandbox
        self.trade_mode = trade_mode
        self.paper_balance = float(paper_balance if paper_balance is not None else DEFAULT_PAPER_BALANCE)
        self.position = None
        self.trade_log = []
        self.trade_logger = logging.getLogger('trade')
        self.persistence_config = persistence_config or {}
        self.persistence_enabled = bool(self.persistence_config.get('enabled', True))
        self.persist_position = bool(self.persistence_config.get('persist_position', True))
        execution_cfg = dict(self.persistence_config.get('execution') or {})
        self.fee_rate = float(execution_cfg.get('fee_rate', 0.0) or 0.0)
        self.slippage_rate = float(execution_cfg.get('slippage_rate', 0.0) or 0.0)
        self.daily_loss_stop_enabled = bool(execution_cfg.get('daily_loss_stop_enabled', False))
        self.daily_loss_stop_threshold = float(execution_cfg.get('daily_loss_stop_threshold', 0.0) or 0.0)
        self.store = None
        if self.persistence_enabled:
            self.store = create_trade_store(self.persistence_config)
            logging.info(
                "交易持久化已启用: backend=%s, target=%s",
                self.store.backend,
                summarize_database_target(self.store.database_url),
            )
        logging.info(
            "交易执行器初始化完成: trade_mode=%s sandbox=%s paper_balance=%s",
            self.trade_mode,
            self.sandbox,
            self.paper_balance,
        )

    def close(self) -> None:
        if self.store is not None:
            self.store.close()
            logging.info("交易持久化已关闭")

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
        logging.info("已从持久化存储恢复本地持仓: %s", self.position)
        return self.position

    def execute_trade_with_risk_management(
        self,
        symbol: str,
        signal: Dict[str, Any],
        data: Dict[str, Any],
        risk_manager,
        trigger_source: str = 'strategy_signal',
        run_id: Optional[int] = None,
        trade_task_profile_id: Optional[int] = None,
    ) -> None:
        logging.info("开始执行交易 - 信号: %s, 置信度: %.2f, 策略: %s", signal['action'], signal.get('confidence', 0), signal.get('strategy', 'unknown'))

        position_before = self._snapshot_position(self.position)
        risk_check = risk_manager.risk_management_check(data, signal)
        if not risk_check['passed']:
            logging.warning("风控检查未通过，取消交易: %s", risk_check['reason'])
            self._persist_trade_record(
                symbol=symbol,
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='risk_rejected',
                result_reason=risk_check['reason'],
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=position_before,
                run_id=run_id,
                trade_task_profile_id=trade_task_profile_id,
            )
            return

        try:
            usdt_balance = self._get_available_usdt_balance()

            if signal['action'] == 'buy' and usdt_balance <= 10:
                reason = 'USDT余额不足，跳过买入'
                logging.info(reason)
                self._persist_trade_record(
                    symbol=symbol,
                    signal=signal,
                    data=data,
                    trigger_source=trigger_source,
                    result='skipped',
                    result_reason=reason,
                    risk_snapshot=risk_check['metrics'],
                    position_before=position_before,
                    position_after=position_before,
                    run_id=run_id,
                    trade_task_profile_id=trade_task_profile_id,
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
                        symbol=symbol,
                        signal=signal,
                        data=data,
                        trigger_source=trigger_source,
                        result='skipped',
                        result_reason=f'交易对 {symbol} 不在交易所市场列表中',
                        requested_amount=amount,
                        risk_snapshot=risk_check['metrics'],
                        position_before=position_before,
                        position_after=position_before,
                        run_id=run_id,
                        trade_task_profile_id=trade_task_profile_id,
                    )
                    return

                market = markets[symbol]
                min_amount = market['limits']['amount']['min'] if 'min' in market['limits']['amount'] else 0
                amount = max(amount, min_amount)
                logging.info("调整后交易数量: %s (最小: %s)", amount, min_amount)

                order = self._submit_buy_order(symbol, amount, data)
                order_summary = self._build_order_summary(order, float(data['price']))
                stop_loss_price = signal.get('stop_loss_price', data['price'] * (1 - stop_loss_pct))
                trailing_stop_price = signal.get('trailing_stop_price')
                self.position = {
                    'entry_time': self._utc_now(),
                    'entry_price': order_summary['fill_price'],
                    'stop_loss': stop_loss_price,
                    'initial_stop_loss': stop_loss_price,
                    'trailing_stop_price': trailing_stop_price,
                    'highest_price': data['price'],
                    'highest_close': data['price'],
                    'amount': float(order_summary['filled_amount'] or amount),
                    'strategy': signal.get('strategy'),
                    'meta': {
                        **dict(signal.get('meta', {})),
                        'entryFee': order_summary['fee'],
                        'entryCost': order_summary['cost'],
                        'entryFillPrice': order_summary['fill_price'],
                        'feeSource': order_summary['fee_source'],
                        'execution': self._execution_snapshot(),
                    },
                }
                trade_id = self._persist_trade_record(
                    symbol=symbol,
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
                    order_summary=order_summary,
                    run_id=run_id,
                    trade_task_profile_id=trade_task_profile_id,
                )
                self._persist_position_state(symbol, self.position, trade_id)
                self._log_trade(signal, order, 'BUY_EXECUTED')
                logging.info("买单执行成功 - 价格: %s, 数量: %s", data['price'], amount)
                return

            if signal['action'] == 'sell' and self.position:
                position_amount = self.position['amount']
                order = self._submit_sell_order(symbol, position_amount, data)
                order_summary = self._build_order_summary(order, float(data['price']))
                realized_metrics = self._calculate_realized_pnl(position_before or {}, order_summary)
                daily_loss_snapshot = self._build_daily_loss_snapshot(run_id, realized_metrics.get('realized_pnl_net'))
                trade_id = self._persist_trade_record(
                    symbol=symbol,
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
                    order_summary=order_summary,
                    realized_metrics=realized_metrics,
                    daily_loss_snapshot=daily_loss_snapshot,
                    run_id=run_id,
                    trade_task_profile_id=trade_task_profile_id,
                )
                self._log_trade(signal, order, 'SELL_EXECUTED')
                self.position = None
                self._delete_position_state(symbol)
                logging.info("卖单执行成功 - 价格: %s, 数量: %s, 记录ID: %s", data['price'], position_amount, trade_id)
                self._raise_if_daily_loss_exceeded(daily_loss_snapshot)
                return

            reason = '不满足交易条件，跳过交易执行'
            logging.info(reason)
            self._persist_trade_record(
                symbol=symbol,
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='skipped',
                result_reason='当前无持仓可卖' if signal['action'] == 'sell' else reason,
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=position_before,
                run_id=run_id,
                trade_task_profile_id=trade_task_profile_id,
            )

        except TradingHaltError:
            raise
        except Exception as e:
            logging.error("交易执行错误: trade_mode=%s error=%s", self.trade_mode, e)
            self._persist_trade_record(
                symbol=symbol,
                signal=signal,
                data=data,
                trigger_source=trigger_source,
                result='failed',
                result_reason='交易执行异常',
                risk_snapshot=risk_check['metrics'],
                position_before=position_before,
                position_after=self._snapshot_position(self.position),
                error_message=str(e),
                run_id=run_id,
                trade_task_profile_id=trade_task_profile_id,
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
            'trade_mode': self.trade_mode,
            'signal': signal,
            'order_id': order.get('id', 'unknown'),
            'price': order.get('price', 'unknown'),
            'amount': order.get('amount', 'unknown'),
        }
        self.trade_log.append(log_entry)
        logging.info("交易日志: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))
        self.trade_logger.info("交易成功: %s", json.dumps(log_entry, indent=2, ensure_ascii=False))

    def _get_available_usdt_balance(self) -> float:
        if self.trade_mode == 'paper':
            logging.info("纸上交易使用本地虚拟USDT余额: %s", self.paper_balance)
            return self.paper_balance

        balance = self.exchange.fetch_balance()
        usdt_balance = float(balance['total'].get('USDT', 0) or 0)
        logging.info("账户USDT余额: %s", usdt_balance)
        return usdt_balance

    def _submit_buy_order(self, symbol: str, amount: float, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.trade_mode == 'paper':
            market_price = float(data['price'])
            fill_price = market_price * (1 + self.slippage_rate)
            cost = float(amount) * fill_price
            fee = cost * self.fee_rate
            self.paper_balance = max(self.paper_balance - cost - fee, 0.0)
            logging.info(
                "纸上交易买入，不调用真实下单: symbol=%s amount=%s fill_price=%s fee=%s remain_balance=%s",
                symbol,
                amount,
                fill_price,
                fee,
                self.paper_balance,
            )
            return self._build_paper_order(symbol=symbol, side='buy', amount=amount, price=fill_price, fee=fee)
        return self.exchange.create_order(symbol, 'market', 'buy', amount)

    def _submit_sell_order(self, symbol: str, amount: float, data: Dict[str, Any]) -> Dict[str, Any]:
        if self.trade_mode == 'paper':
            market_price = float(data['price'])
            fill_price = market_price * (1 - self.slippage_rate)
            income = float(amount) * fill_price
            fee = income * self.fee_rate
            self.paper_balance += income - fee
            logging.info(
                "纸上交易卖出，不调用真实下单: symbol=%s amount=%s fill_price=%s fee=%s new_balance=%s",
                symbol,
                amount,
                fill_price,
                fee,
                self.paper_balance,
            )
            return self._build_paper_order(symbol=symbol, side='sell', amount=amount, price=fill_price, fee=fee)
        return self.exchange.create_order(symbol, 'market', 'sell', amount)

    def _build_paper_order(self, symbol: str, side: str, amount: float, price: float, fee: float) -> Dict[str, Any]:
        return {
            'id': f'paper-{side}-{int(datetime.now(timezone.utc).timestamp() * 1000)}',
            'status': 'closed',
            'type': 'market',
            'side': side,
            'symbol': symbol,
            'price': price,
            'average': price,
            'amount': amount,
            'cost': amount * price,
            'filled': amount,
            'remaining': 0.0,
            'fee': {
                'cost': fee,
                'currency': 'USDT',
            },
            'clientOrderId': 'paper-trading',
        }

    def _persist_trade_record(
        self,
        symbol: str,
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
        order_summary: Optional[Dict[str, Any]] = None,
        realized_metrics: Optional[Dict[str, Any]] = None,
        daily_loss_snapshot: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        run_id: Optional[int] = None,
        trade_task_profile_id: Optional[int] = None,
    ) -> Optional[int]:
        if self.store is None:
            return None

        record = {
            'created_at': self._utc_now(),
            'run_id': run_id,
            'trade_task_profile_id': trade_task_profile_id,
            'symbol': symbol,
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
            'trade_mode': self.trade_mode,
            'fee_rate': self.fee_rate,
            'slippage_rate': self.slippage_rate,
            'result': result,
            'result_reason': result_reason,
            'estimated_fill_price': order_summary.get('fill_price') if order_summary else None,
            'estimated_fee': order_summary.get('fee') if order_summary else None,
            'realized_pnl': realized_metrics.get('realized_pnl') if realized_metrics else None,
            'realized_pnl_net': realized_metrics.get('realized_pnl_net') if realized_metrics else None,
            'error_message': error_message,
            'daily_loss_snapshot': daily_loss_snapshot,
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

    def _build_order_summary(self, order: Dict[str, Any], market_price: float) -> Dict[str, Any]:
        fill_price = self._to_float(order.get('average')) or self._to_float(order.get('price')) or market_price
        filled_amount = self._to_float(order.get('filled')) or self._to_float(order.get('amount')) or 0.0
        cost = self._to_float(order.get('cost')) or (filled_amount * fill_price)
        fee_value = self._extract_fee_value(order)
        fee_source = 'actual' if fee_value is not None else 'estimated'
        fee = float(fee_value if fee_value is not None else cost * self.fee_rate)
        return {
            'fill_price': float(fill_price),
            'filled_amount': float(filled_amount),
            'cost': float(cost),
            'fee': fee,
            'fee_source': fee_source,
        }

    def _extract_fee_value(self, order: Dict[str, Any]) -> Optional[float]:
        fee = order.get('fee')
        if isinstance(fee, dict):
            cost = self._to_float(fee.get('cost'))
            if cost is not None:
                return cost
        fees = order.get('fees')
        if isinstance(fees, list):
            total = 0.0
            found = False
            for item in fees:
                if not isinstance(item, dict):
                    continue
                cost = self._to_float(item.get('cost'))
                if cost is None:
                    continue
                total += cost
                found = True
            if found:
                return total
        return None

    def _calculate_realized_pnl(self, position_before: Dict[str, Any], order_summary: Dict[str, Any]) -> Dict[str, Any]:
        amount = float(order_summary.get('filled_amount') or 0.0)
        fill_price = float(order_summary.get('fill_price') or 0.0)
        gross_proceeds = amount * fill_price
        exit_fee = float(order_summary.get('fee') or 0.0)
        net_proceeds = gross_proceeds - exit_fee
        entry_price = float(position_before.get('entry_price') or 0.0)
        entry_fee = self._to_float((position_before.get('meta') or {}).get('entryFee')) or 0.0
        cost_basis = amount * entry_price
        total_cost_basis = cost_basis + entry_fee
        realized_pnl = gross_proceeds - cost_basis
        realized_pnl_net = net_proceeds - total_cost_basis
        return {
            'realized_pnl': realized_pnl,
            'realized_pnl_net': realized_pnl_net,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'gross_proceeds': gross_proceeds,
            'net_proceeds': net_proceeds,
        }

    def _build_daily_loss_snapshot(self, run_id: Optional[int], realized_pnl_net: Optional[float]) -> Optional[Dict[str, Any]]:
        if self.store is None or run_id is None:
            return None
        day_start = self._utc_day_start()
        day_end = (datetime.fromisoformat(day_start) + timedelta(days=1)).isoformat()
        summary = self.store.get_daily_loss_summary(run_id, day_start, day_end)
        realized_loss = float(summary.get('realizedLoss') or 0.0)
        if realized_pnl_net is not None and realized_pnl_net < 0:
            realized_loss += abs(float(realized_pnl_net))
            summary['realizedPnlNet'] = float(summary.get('realizedPnlNet') or 0.0) + float(realized_pnl_net)
            summary['tradeCount'] = int(summary.get('tradeCount') or 0) + 1
        summary['realizedLoss'] = realized_loss
        summary['threshold'] = self.daily_loss_stop_threshold
        summary['enabled'] = self.daily_loss_stop_enabled
        summary['triggered'] = bool(
            self.daily_loss_stop_enabled
            and self.daily_loss_stop_threshold > 0
            and realized_loss >= self.daily_loss_stop_threshold
        )
        return summary

    def _raise_if_daily_loss_exceeded(self, summary: Optional[Dict[str, Any]]) -> None:
        if not summary or not summary.get('triggered'):
            return
        logging.warning(
            '触发单日亏损停机: run_id=%s realized_loss=%s threshold=%s trade_mode=%s',
            summary.get('runId'),
            summary.get('realizedLoss'),
            summary.get('threshold'),
            self.trade_mode,
        )
        raise TradingHaltError('daily_loss_stop_triggered', summary)

    def check_daily_loss_stop(self, run_id: Optional[int]) -> Optional[Dict[str, Any]]:
        summary = self._build_daily_loss_snapshot(run_id, None)
        self._raise_if_daily_loss_exceeded(summary)
        return summary

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

    def _execution_snapshot(self) -> Dict[str, Any]:
        return {
            'feeRate': self.fee_rate,
            'slippageRate': self.slippage_rate,
            'dailyLossStopEnabled': self.daily_loss_stop_enabled,
            'dailyLossStopThreshold': self.daily_loss_stop_threshold,
        }

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

    @staticmethod
    def _utc_day_start() -> str:
        now = datetime.now(timezone.utc)
        day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        return day_start.isoformat()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_position(self) -> Dict[str, Any]:
        logging.debug("获取当前持仓: %s", self.position)
        return self.position

    def set_position(self, position: Dict[str, Any]) -> None:
        self.position = position
        logging.info("持仓已更新: %s", position)
