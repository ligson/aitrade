from .btc_spot_breakout_strategy import BTCSpotBreakoutStrategy
from .btc_spot_trend_breakout_strategy import BTCSpotTrendBreakoutStrategy
from .gpt_strategy import GPTStrategy


def create_strategy(config):
    strategy_type = config.trade_strategy_type

    if strategy_type == 'gpt':
        return GPTStrategy(config)

    if strategy_type == 'btc_spot_breakout':
        return BTCSpotBreakoutStrategy(config.trade_strategy_btc_spot_config)

    if strategy_type == 'btc_spot_trend_breakout':
        return BTCSpotTrendBreakoutStrategy(config.trade_strategy_btc_spot_trend_breakout_config)

    raise ValueError(f'不支持的交易策略类型: {strategy_type}')
