from __future__ import annotations

from typing import Any

from ...config.config_file import DEFAULT_BTC_SPOT_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_GPT_STRATEGY_CONFIG


_STRATEGY_DEFINITIONS: list[dict[str, Any]] = [
    {
        'strategyType': 'gpt',
        'displayName': 'GPT AI 策略',
        'description': '通过兼容 OpenAI 接口的模型分析行情并生成交易信号。',
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
    }
