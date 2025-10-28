import json
import logging
import os
import time
from datetime import datetime

import ccxt
import numpy as np
import pandas as pd

from trade.gpt_signal import get_ai_signal


def calculate_technical_indicators(closes, highs, lows, volumes):
    """计算完整的技术指标"""

    # RSI
    def compute_rsi(prices, period=14):
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / (down + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        for i in range(period, len(deltas)):
            delta = deltas[i]
            up = (up * (period - 1) + max(delta, 0)) / period
            down = (down * (period - 1) + max(-delta, 0)) / period
            rs = up / (down + 1e-10)
            rsi = np.append(rsi, 100 - (100 / (1 + rs)))

        return rsi

    # MACD
    ema12 = pd.Series(closes).ewm(span=12).mean().values
    ema26 = pd.Series(closes).ewm(span=26).mean().values
    macd_line = ema12 - ema26
    signal_line = pd.Series(macd_line).ewm(span=9).mean().values
    macd_histogram = macd_line - signal_line

    # 支撑阻力
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])

    # 成交量分析
    volume_avg = np.mean(volumes[-20:])
    volume_trend = "上升" if volumes[-1] > volume_avg else "下降"

    return {
        'rsi': compute_rsi(closes)[-1] if len(closes) > 14 else 50,
        'macd_line': macd_line[-1],
        'macd_signal': signal_line[-1],
        'macd_histogram': macd_histogram[-1],
        'macd_trend': " bullish" if macd_histogram[-1] > 0 else "bearish",
        'resistance': recent_high,
        'support': recent_low,
        'volume_trend': volume_trend,
        'price_vs_ma': "above" if closes[-1] > np.mean(closes[-20:]) else "below"
    }


def risk_management_check(data, proposed_action):
    """风险管理检查"""
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


def calculate_position_size(balance, risk_per_trade=0.02, stop_loss_pct=0.05):
    """根据账户余额和风险承受能力计算仓位大小"""
    risk_amount = balance * risk_per_trade
    position_size = risk_amount / stop_loss_pct
    return min(position_size, balance * 0.1)  # 单次交易不超过总资金的10%


def check_market_conditions(volumes, volatility_threshold=0.03):
    """检查市场条件"""
    recent_volatility = np.std(volumes[-10:]) / np.mean(volumes[-10:])
    return recent_volatility < volatility_threshold


class OptimizedCryptoBot:
    def __init__(self):
        config = {
            'apiKey': os.getenv('BINANCE_API_KEY'),
            'secret': os.getenv('BINANCE_SECRET_KEY'),
            'sandbox': bool(os.getenv('SANDBOX_TRADE')),
            'enableRateLimit': True
        }
        # 检查环境变量中是否有代理设置
        http_proxy = os.getenv('http_proxy') or os.getenv('HTTP_PROXY')

        # 如果环境变量中有代理设置，则使用代理
        if http_proxy:
            config['proxies'] = {
                'http': http_proxy,
                'https': http_proxy
            }
        self.exchange = ccxt.binance(config)
        self.position = None
        self.trade_log = []

    def get_enhanced_market_data(self, symbol='BTC/USDT', timeframe='15m', limit=100):
        """获取增强的市场数据"""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]

        technicals = calculate_technical_indicators(closes, highs, lows, volumes)

        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': closes[-1],
            'closes': closes,
            'volumes': volumes,
            'technicals': technicals
        }

    def execute_trade_with_risk_management(self, symbol, signal, data):
        """带风险管理的交易执行"""
        if not risk_management_check(data, signal['action']):
            print("风控检查未通过，取消交易")
            return

        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total']['USDT']

            if signal['action'] == 'buy' and usdt_balance > 10:
                amount = calculate_position_size(
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
                self.position = {'entry_price': data['price'],
                                 'stop_loss': data['price'] * (1 - signal['stop_loss_pct'])}
                self.log_trade(signal, order, 'BUY_EXECUTED')

            elif signal['action'] == 'sell' and self.position:
                # 简化卖出逻辑
                order = self.exchange.create_order(
                    symbol, 'market', 'sell', self.position['amount']
                )
                self.log_trade(signal, order, 'SELL_EXECUTED')
                self.position = None

        except Exception as e:
            print(f"交易执行错误: {e}")

    def log_trade(self, signal, order, action):
        """交易日志"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'signal': signal,
            'order_id': order['id'],
            'price': order['price'],
            'amount': order['amount']
        }
        self.trade_log.append(log_entry)
        print(f"交易日志: {json.dumps(log_entry, indent=2)}")

    def run(self):
        """主循环"""
        logging.info("启动优化版交易机器人...")

        while True:
            try:
                # 获取市场数据
                data = self.get_enhanced_market_data()

                # 获取AI信号
                signal = get_ai_signal(data)
                print(f"AI信号: {signal}")

                # 执行交易
                if signal['action'] != 'hold' and signal.get('confidence', 0) > 0.7:
                    self.execute_trade_with_risk_management('BTC/USDT', signal, data)

                # 监控止损
                if self.position and data['price'] <= self.position['stop_loss']:
                    print("触发止损!")
                    # 执行止损逻辑

                time.sleep(900)  # 15分钟

            except Exception as e:
                print(f"主循环错误: {e}")
                time.sleep(60)



