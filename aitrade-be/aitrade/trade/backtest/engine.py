from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from typing import Callable

from ..strategies.btc_spot_breakout_strategy import BTCSpotBreakoutStrategy
from ..strategies.btc_spot_trend_breakout_strategy import BTCSpotTrendBreakoutStrategy


class BacktestStoppedError(Exception):
    pass


@dataclass
class BacktestTrade:
    bar_time: str
    side: str
    price: float
    quantity: float
    fee: float
    pnl: float | None
    reason: str
    signal: dict[str, Any]
    position: dict[str, Any]


class BacktestEngine:
    def __init__(self, fee_rate: float, initial_balance: float, slippage_rate: float = 0.0):
        self.fee_rate = fee_rate
        self.initial_balance = initial_balance
        self.slippage_rate = slippage_rate

    def run_backtest(
        self,
        strategy_type: str,
        dataset: dict[str, Any],
        symbol: str,
        timeframe: str,
        strategy_params: dict[str, Any],
        timerange_from: str,
        timerange_to: str,
        should_stop: Callable[[], bool] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        strategy = self._create_strategy(strategy_type, strategy_params)
        primary_bars = list(dataset.get('primary_bars') or [])
        context_bars = dict(dataset.get('context_bars') or {})
        required_history = strategy.get_required_history()
        context_history_getter = getattr(strategy, 'get_required_context_history', None)
        required_context_history = context_history_getter() if callable(context_history_getter) else {}

        balance = float(self.initial_balance)
        peak_equity = balance
        max_drawdown = 0.0
        position: dict[str, Any] | None = None
        trades: list[BacktestTrade] = []
        equity_curve: list[float] = []

        timestamps: list[str] = []
        opens: list[float] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        volumes: list[float] = []

        filtered_rows = []
        for row in primary_bars:
            if not isinstance(row, list) or len(row) < 6:
                continue
            timestamp_ms = int(row[0])
            bar_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()
            if bar_time < timerange_from or bar_time > timerange_to:
                continue
            filtered_rows.append((row, bar_time))
        total_bars = len(filtered_rows)
        processed_bars = 0
        progress_interval = 50

        for row, bar_time in filtered_rows:
            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
            volume = float(row[5])
            decision_ts = int(row[0])

            processed_bars += 1
            timestamps.append(bar_time)
            opens.append(open_price)
            highs.append(high_price)
            lows.append(low_price)
            closes.append(close_price)
            volumes.append(volume)

            if on_progress and (
                processed_bars == 1
                or processed_bars % progress_interval == 0
                or processed_bars == total_bars
            ):
                on_progress(processed_bars, total_bars)

            if should_stop and (
                processed_bars == 1
                or processed_bars % progress_interval == 0
                or processed_bars == total_bars
            ) and should_stop():
                raise BacktestStoppedError('用户已停止任务')

            market_data = {
                'symbol': symbol,
                'timestamp': bar_time,
                'price': close_price,
                'timestamps': timestamps,
                'opens': opens,
                'highs': highs,
                'lows': lows,
                'closes': closes,
                'volumes': volumes,
                'ohlcv': [item[0] for item in filtered_rows[:processed_bars]],
            }
            contexts = {}
            enough_context = True
            for context_timeframe, rows in context_bars.items():
                context_market_data = self._build_context_market_data(rows, decision_ts)
                contexts[context_timeframe] = context_market_data
                if len(context_market_data.get('closes', [])) < int(required_context_history.get(context_timeframe, 0) or 0):
                    enough_context = False
            if contexts:
                market_data['primary'] = dict(market_data)
                market_data['contexts'] = contexts
                market_data['decisionTimestamp'] = decision_ts

            if len(closes) < required_history or not enough_context:
                equity = balance + ((position['amount'] * close_price) if position else 0.0)
                equity_curve.append(equity)
                peak_equity = max(peak_equity, equity)
                if peak_equity > 0:
                    max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)
                continue

            signal = strategy.generate_signal(market_data, position)
            action = signal.get('action')
            if action == 'buy' and position is None:
                cash_to_use = balance
                if cash_to_use > 0:
                    filled_price = close_price * (1 + self.slippage_rate)
                    fee = cash_to_use * self.fee_rate
                    quantity = max((cash_to_use - fee) / filled_price, 0.0)
                    if quantity > 0:
                        balance = 0.0
                        position = {
                            'symbol': symbol,
                            'strategy': signal.get('strategy', strategy_type),
                            'entry_time': bar_time,
                            'entry_price': filled_price,
                            'amount': quantity,
                            'stop_loss': signal.get('stop_loss_price'),
                            'initial_stop_loss': signal.get('stop_loss_price'),
                            'trailing_stop_price': signal.get('trailing_stop_price'),
                            'highest_price': close_price,
                            'highest_close': close_price,
                            'meta': signal.get('meta', {}),
                        }
                        trade_signal = dict(signal)
                        trade_signal.setdefault('meta', {})
                        trade_signal['meta'] = {
                            **dict(trade_signal.get('meta') or {}),
                            'bar_close_price': close_price,
                            'filled_price': filled_price,
                            'slippage_rate': self.slippage_rate,
                        }
                        trades.append(
                            BacktestTrade(
                                bar_time=bar_time,
                                side='buy',
                                price=filled_price,
                                quantity=quantity,
                                fee=fee,
                                pnl=None,
                                reason=str(signal.get('reason', '')),
                                signal=trade_signal,
                                position=dict(position),
                            )
                        )
            elif action == 'sell' and position is not None:
                filled_price = close_price * (1 - self.slippage_rate)
                gross = position['amount'] * filled_price
                fee = gross * self.fee_rate
                net = gross - fee
                cost_basis = position['amount'] * position['entry_price']
                pnl = net - cost_basis
                balance = net
                sell_position = dict(position)
                trade_signal = dict(signal)
                trade_signal.setdefault('meta', {})
                trade_signal['meta'] = {
                    **dict(trade_signal.get('meta') or {}),
                    'bar_close_price': close_price,
                    'filled_price': filled_price,
                    'slippage_rate': self.slippage_rate,
                }
                trades.append(
                    BacktestTrade(
                        bar_time=bar_time,
                        side='sell',
                        price=filled_price,
                        quantity=position['amount'],
                        fee=fee,
                        pnl=pnl,
                        reason=str(signal.get('reason', '')),
                        signal=trade_signal,
                        position=sell_position,
                    )
                )
                position = None
            elif position is not None:
                position['stop_loss'] = signal.get('stop_loss_price', position.get('stop_loss'))
                position['trailing_stop_price'] = signal.get('trailing_stop_price', position.get('trailing_stop_price'))
                position['highest_price'] = max(float(position.get('highest_price', close_price)), high_price, close_price)
                position['highest_close'] = max(float(position.get('highest_close', close_price)), close_price)
                position['meta'] = signal.get('meta', position.get('meta', {}))

            equity = balance + ((position['amount'] * close_price) if position else 0.0)
            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            if peak_equity > 0:
                max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)

        if position is not None and closes:
            close_price = closes[-1]
            filled_price = close_price * (1 - self.slippage_rate)
            gross = position['amount'] * filled_price
            fee = gross * self.fee_rate
            net = gross - fee
            cost_basis = position['amount'] * position['entry_price']
            pnl = net - cost_basis
            balance = net
            trades.append(
                BacktestTrade(
                    bar_time=timestamps[-1],
                    side='sell',
                    price=filled_price,
                    quantity=position['amount'],
                    fee=fee,
                    pnl=pnl,
                    reason='回测结束自动平仓',
                    signal={
                        'action': 'sell',
                        'reason': '回测结束自动平仓',
                        'strategy': strategy_type,
                        'meta': {
                            'bar_close_price': close_price,
                            'filled_price': filled_price,
                            'slippage_rate': self.slippage_rate,
                        },
                    },
                    position=dict(position),
                )
            )
            position = None

        sell_trades = [item for item in trades if item.side == 'sell' and item.pnl is not None]
        wins = [item for item in sell_trades if (item.pnl or 0) > 0]
        final_equity = balance
        total_return = ((final_equity - self.initial_balance) / self.initial_balance) if self.initial_balance > 0 else 0.0
        summary = {
            'symbol': symbol,
            'timeframe': timeframe,
            'initialBalance': self.initial_balance,
            'finalEquity': final_equity,
            'totalReturn': total_return,
            'maxDrawdown': max_drawdown,
            'tradeCount': len(trades),
            'completedTradeCount': len(sell_trades),
            'winRate': (len(wins) / len(sell_trades)) if sell_trades else 0.0,
            'requiredHistory': required_history,
            'slippageRate': self.slippage_rate,
        }
        return {
            'summary': summary,
            'trades': [
                {
                    'barTime': item.bar_time,
                    'side': item.side,
                    'price': item.price,
                    'quantity': item.quantity,
                    'fee': item.fee,
                    'pnl': item.pnl,
                    'reason': item.reason,
                    'signal': item.signal,
                    'position': item.position,
                    'createdAt': item.bar_time,
                }
                for item in trades
            ],
        }

    @staticmethod
    def _create_strategy(strategy_type: str, strategy_params: dict[str, Any]):
        if strategy_type == 'btc_spot_breakout':
            return BTCSpotBreakoutStrategy(strategy_params)
        if strategy_type == 'btc_spot_trend_breakout':
            return BTCSpotTrendBreakoutStrategy(strategy_params)
        raise ValueError(f'当前回测暂不支持策略类型: {strategy_type}')

    @staticmethod
    def _build_context_market_data(rows: list[list[Any]], decision_ts: int) -> dict[str, Any]:
        filtered_rows = [row for row in rows if isinstance(row, list) and len(row) >= 6 and int(row[0]) <= decision_ts]
        timestamps = [int(item[0]) for item in filtered_rows]
        opens = [float(item[1]) for item in filtered_rows]
        highs = [float(item[2]) for item in filtered_rows]
        lows = [float(item[3]) for item in filtered_rows]
        closes = [float(item[4]) for item in filtered_rows]
        volumes = [float(item[5]) for item in filtered_rows]
        return {
            'timestamps': timestamps,
            'opens': opens,
            'highs': highs,
            'lows': lows,
            'closes': closes,
            'volumes': volumes,
            'ohlcv': filtered_rows,
            'price': closes[-1] if closes else None,
        }
