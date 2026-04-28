from __future__ import annotations

from typing import Any

from ...config.config_file import DEFAULT_BTC_SPOT_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_GPT_STRATEGY_CONFIG
from .fusion_profile import DEFAULT_SPOT_MULTI_SIGNAL_FUSION_PROFILE_CONFIG


_STRATEGY_DEFINITIONS: list[dict[str, Any]] = [
    {
        'strategyType': 'gpt',
        'displayName': 'GPT AI 策略',
        'description': '通过兼容 OpenAI 接口的模型分析行情并生成交易信号。',
        'backtestSupported': False,
        'strategyCategory': 'gpt',
        'configMode': 'flat_params',
        'usableAsFusionNode': False,
        'supportsSpot': True,
        'supportsPaper': True,
        'supportsBacktest': False,
        'fixedConstraints': [],
        'defaultParams': dict(DEFAULT_GPT_STRATEGY_CONFIG),
        'paramSchema': [
            {
                'field': 'min_confidence',
                'label': '最低置信度',
                'type': 'number',
                'required': True,
                'min': 0,
                'max': 1,
                'step': 0.01,
                'description': '当模型信号置信度低于该值时自动转为观望。',
            },
        ],
        'schemaVersion': 1,
    },
    {
        'strategyType': 'btc_spot_breakout',
        'displayName': 'BTC 现货突破策略',
        'description': '基于 Donchian 通道、EMA 趋势、ATR 止损和成交量确认的 BTC 现货 long-only 规则策略。',
        'backtestSupported': True,
        'strategyCategory': 'kline',
        'configMode': 'flat_params',
        'usableAsFusionNode': True,
        'supportsSpot': True,
        'supportsPaper': True,
        'supportsBacktest': True,
        'fixedConstraints': [],
        'defaultParams': dict(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG),
        'paramSchema': [
            {'field': 'donchian_entry', 'label': '突破入场窗口', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'donchian_exit', 'label': '跌破出场窗口', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'ema_period', 'label': 'EMA 周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'ema_slope_lookback', 'label': 'EMA 斜率回看', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'atr_period', 'label': 'ATR 周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'atr_stop_mult', 'label': '初始止损 ATR 倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'atr_trail_mult', 'label': '追踪止损 ATR 倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'breakout_buffer_bps', 'label': '突破缓冲 bps', 'type': 'number', 'required': True, 'min': 0, 'step': 0.1},
            {'field': 'confirm_macd', 'label': '启用 MACD 确认', 'type': 'boolean', 'required': True},
            {'field': 'confirm_volume', 'label': '启用成交量确认', 'type': 'boolean', 'required': True},
            {'field': 'volume_ma_period', 'label': '成交量均线周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'volume_multiplier', 'label': '成交量放大倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'default_risk_per_trade', 'label': '单笔风险比例', 'type': 'number', 'required': True, 'min': 0.0001, 'max': 1, 'step': 0.0001},
        ],
        'schemaVersion': 1,
    },
    {
        'strategyType': 'btc_spot_trend_breakout',
        'displayName': 'BTC 现货趋势突破策略',
        'description': '基于 4h EMA/ADX 趋势过滤与 1h 突破放量入场的 BTC 现货 long-only 规则策略。',
        'backtestSupported': True,
        'strategyCategory': 'kline',
        'configMode': 'flat_params',
        'usableAsFusionNode': True,
        'supportsSpot': True,
        'supportsPaper': True,
        'supportsBacktest': True,
        'fixedConstraints': ['task_timeframe=1h', 'requires_context=4h'],
        'defaultParams': dict(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG),
        'paramSchema': [
            {'field': 'ema_fast_period', 'label': '趋势快 EMA 周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'ema_slow_period', 'label': '趋势慢 EMA 周期', 'type': 'integer', 'required': True, 'min': 2},
            {'field': 'adx_period', 'label': 'ADX 周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'adx_threshold', 'label': 'ADX 阈值', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'breakout_lookback', 'label': '突破窗口', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'volume_ma_period', 'label': '成交量均线周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'volume_multiplier', 'label': '成交量放大倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'atr_period', 'label': 'ATR 周期', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'atr_stop_mult', 'label': '初始止损 ATR 倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'atr_trail_mult', 'label': '追踪止损 ATR 倍数', 'type': 'number', 'required': True, 'min': 0.01, 'step': 0.01},
            {'field': 'default_risk_per_trade', 'label': '单笔风险比例', 'type': 'number', 'required': True, 'min': 0.0001, 'max': 1, 'step': 0.0001},
        ],
        'schemaVersion': 1,
    },
    {
        'strategyType': 'spot_multi_signal_fusion',
        'displayName': '现货多源融合策略',
        'description': '面向现货的结构化融合策略，可选择已有 K 线策略与信号源档案参与编排，优先用于 paper 实时模拟验证。',
        'backtestSupported': False,
        'strategyCategory': 'fusion',
        'configMode': 'structured',
        'usableAsFusionNode': False,
        'supportsSpot': True,
        'supportsPaper': True,
        'supportsBacktest': False,
        'fixedConstraints': [],
        'defaultParams': dict(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_PROFILE_CONFIG),
        'paramSchema': [],
        'schemaVersion': 3,
    },
]


_definitions_by_type = {item['strategyType']: item for item in _STRATEGY_DEFINITIONS}


def list_strategy_definitions() -> list[dict[str, Any]]:
    return [
        {
            'strategyType': item['strategyType'],
            'displayName': item['displayName'],
            'description': item['description'],
            'defaultParams': dict(item['defaultParams']),
            'paramSchema': [dict(field) for field in item['paramSchema']],
            'schemaVersion': item['schemaVersion'],
            'backtestSupported': item.get('backtestSupported', False),
            'strategyCategory': item.get('strategyCategory', ''),
            'configMode': item.get('configMode', 'flat_params'),
            'usableAsFusionNode': bool(item.get('usableAsFusionNode', False)),
            'supportsSpot': bool(item.get('supportsSpot', True)),
            'supportsPaper': bool(item.get('supportsPaper', True)),
            'supportsBacktest': bool(item.get('supportsBacktest', item.get('backtestSupported', False))),
            'fixedConstraints': list(item.get('fixedConstraints') or []),
        }
        for item in _STRATEGY_DEFINITIONS
    ]


def get_strategy_definition(strategy_type: str) -> dict[str, Any]:
    item = _definitions_by_type.get(strategy_type)
    if item is None:
        raise ValueError(f'不支持的交易策略类型: {strategy_type}')
    return {
        'strategyType': item['strategyType'],
        'displayName': item['displayName'],
        'description': item['description'],
        'defaultParams': dict(item['defaultParams']),
        'paramSchema': [dict(field) for field in item['paramSchema']],
        'schemaVersion': item['schemaVersion'],
        'backtestSupported': item.get('backtestSupported', False),
        'strategyCategory': item.get('strategyCategory', ''),
        'configMode': item.get('configMode', 'flat_params'),
        'usableAsFusionNode': bool(item.get('usableAsFusionNode', False)),
        'supportsSpot': bool(item.get('supportsSpot', True)),
        'supportsPaper': bool(item.get('supportsPaper', True)),
        'supportsBacktest': bool(item.get('supportsBacktest', item.get('backtestSupported', False))),
        'fixedConstraints': list(item.get('fixedConstraints') or []),
    }
