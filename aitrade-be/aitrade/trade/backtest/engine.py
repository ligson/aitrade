from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ..strategies.btc_spot_breakout_strategy import BTCSpotBreakoutStrategy


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
    def __init__(self, fee_rate: float, initial_balance: float):
        self.fee_rate = fee_rate
        self.initial_balance = initial_balance

    def run_breakout_backtest(
        self,
        bars: list[list[Any]],
        symbol: str,
        timeframe: str,
        strategy_params: dict[str, Any],
        timerange_from: str,
        timerange_to: str,
    ) -> dict[str, Any]:
        strategy = BTCSpotBreakoutStrategy(strategy_params)
        required_history = strategy.get_required_history()
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

        for row in bars:
            if not isinstance(row, list) or len(row) < 6:
                continue
            timestamp_ms = int(row[0])
            bar_time = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()
            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
            volume = float(row[5])

            if bar_time < timerange_from or bar_time > timerange_to:
                continue

            timestamps.append(bar_time)
            opens.append(open_price)
            highs.append(high_price)
            lows.append(low_price)
            closes.append(close_price)
            volumes.append(volume)

            if len(closes) < required_history:
                equity = balance + ((position['amount'] * close_price) if position else 0.0)
                equity_curve.append(equity)
                peak_equity = max(peak_equity, equity)
                if peak_equity > 0:
                    max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)
                continue

            signal = strategy.generate_signal(
                {
                    'timestamps': timestamps,
                    'opens': opens,
                    'highs': highs,
                    'lows': lows,
                    'closes': closes,
                    'volumes': volumes,
                    'ohlcv': bars,
                },
                position,
            )

            action = signal.get('action')
            if action == 'buy' and position is None:
                cash_to_use = balance
                if cash_to_use > 0:
                    fee = cash_to_use * self.fee_rate
                    quantity = max((cash_to_use - fee) / close_price, 0.0)
                    if quantity > 0:
                        balance = 0.0
                        position = {
                            'symbol': symbol,
                            'strategy': signal.get('strategy', 'btc_spot_breakout'),
                            'entry_time': bar_time,
                            'entry_price': close_price,
                            'amount': quantity,
                            'stop_loss': signal.get('stop_loss_price'),
                            'initial_stop_loss': signal.get('stop_loss_price'),
                            'trailing_stop_price': signal.get('trailing_stop_price'),
                            'highest_price': close_price,
                            'highest_close': close_price,
                            'meta': signal.get('meta', {}),
                        }
                        trades.append(
                            BacktestTrade(
                                bar_time=bar_time,
                                side='buy',
                                price=close_price,
                                quantity=quantity,
                                fee=fee,
                                pnl=None,
                                reason=str(signal.get('reason', '')),
                                signal=signal,
                                position=dict(position),
                            )
                        )
            elif action == 'sell' and position is not None:
                gross = position['amount'] * close_price
                fee = gross * self.fee_rate
                net = gross - fee
                cost_basis = position['amount'] * position['entry_price']
                pnl = net - cost_basis
                balance = net
                sell_position = dict(position)
                trades.append(
                    BacktestTrade(
                        bar_time=bar_time,
                        side='sell',
                        price=close_price,
                        quantity=position['amount'],
                        fee=fee,
                        pnl=pnl,
                        reason=str(signal.get('reason', '')),
                        signal=signal,
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
            gross = position['amount'] * close_price
            fee = gross * self.fee_rate
            net = gross - fee
            cost_basis = position['amount'] * position['entry_price']
            pnl = net - cost_basis
            balance = net
            trades.append(
                BacktestTrade(
                    bar_time=timestamps[-1],
                    side='sell',
                    price=close_price,
                    quantity=position['amount'],
                    fee=fee,
                    pnl=pnl,
                    reason='回测结束自动平仓',
                    signal={'action': 'sell', 'reason': '回测结束自动平仓', 'strategy': 'btc_spot_breakout'},
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
