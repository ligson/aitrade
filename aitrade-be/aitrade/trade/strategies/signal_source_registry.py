from __future__ import annotations

from typing import Any

_SIGNAL_SOURCE_DEFINITIONS: list[dict[str, Any]] = [
    {
        'sourceType': 'trade_flow',
        'displayName': '成交流信号源',
        'description': '基于近期逐笔成交统计买卖占比、名义金额失衡度等信息的实时信号源。',
        'defaultParams': {
            'freshness_seconds': 120,
            'lookback_trades': 200,
        },
        'paramSchema': [
            {'field': 'freshness_seconds', 'label': '新鲜度秒数', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'lookback_trades', 'label': '回看成交数', 'type': 'integer', 'required': True, 'min': 20},
        ],
        'schemaVersion': 1,
        'runtimeSupported': True,
    },
    {
        'sourceType': 'news',
        'displayName': '新闻信号源',
        'description': '预留给新闻摘要、快讯聚合等外部信息输入，第一阶段仅提供配置落点。',
        'defaultParams': {
            'provider_name': '',
            'keywords': '',
            'freshness_seconds': 300,
        },
        'paramSchema': [
            {'field': 'provider_name', 'label': '提供方名称', 'type': 'string', 'required': False},
            {'field': 'keywords', 'label': '关键词', 'type': 'string', 'required': False},
            {'field': 'freshness_seconds', 'label': '新鲜度秒数', 'type': 'integer', 'required': True, 'min': 1},
        ],
        'schemaVersion': 1,
        'runtimeSupported': False,
    },
    {
        'sourceType': 'indicator',
        'displayName': '指标信号源',
        'description': '预留给独立技术指标或衍生信号输出节点，第一阶段仅提供配置落点。',
        'defaultParams': {
            'indicator_key': '',
            'primary_timeframe': '1h',
        },
        'paramSchema': [
            {'field': 'indicator_key', 'label': '指标标识', 'type': 'string', 'required': False},
            {'field': 'primary_timeframe', 'label': '主周期', 'type': 'string', 'required': False},
        ],
        'schemaVersion': 1,
        'runtimeSupported': False,
    },
    {
        'sourceType': 'market_activity',
        'displayName': '市场动态信号源',
        'description': '预留给盘口、波动、成交活跃度等市场动态信号，第一阶段仅提供配置落点。',
        'defaultParams': {
            'activity_window_minutes': 60,
            'min_change_ratio': 0.01,
        },
        'paramSchema': [
            {'field': 'activity_window_minutes', 'label': '观察窗口分钟数', 'type': 'integer', 'required': True, 'min': 1},
            {'field': 'min_change_ratio', 'label': '最小变化比例', 'type': 'number', 'required': True, 'min': 0, 'max': 1, 'step': 0.0001},
        ],
        'schemaVersion': 1,
        'runtimeSupported': False,
    },
    {
        'sourceType': 'external_signal',
        'displayName': '外部信号源',
        'description': '预留给第三方策略、告警或人工分析结果接入，第一阶段仅提供配置落点。',
        'defaultParams': {
            'source_name': '',
            'channel': '',
        },
        'paramSchema': [
            {'field': 'source_name', 'label': '来源名称', 'type': 'string', 'required': False},
            {'field': 'channel', 'label': '渠道标识', 'type': 'string', 'required': False},
        ],
        'schemaVersion': 1,
        'runtimeSupported': False,
    },
]

_definitions_by_type = {item['sourceType']: item for item in _SIGNAL_SOURCE_DEFINITIONS}



def list_signal_source_definitions() -> list[dict[str, Any]]:
    return [
        {
            'sourceType': item['sourceType'],
            'displayName': item['displayName'],
            'description': item['description'],
            'defaultParams': dict(item['defaultParams']),
            'paramSchema': [dict(field) for field in item['paramSchema']],
            'schemaVersion': item['schemaVersion'],
            'runtimeSupported': bool(item.get('runtimeSupported', False)),
        }
        for item in _SIGNAL_SOURCE_DEFINITIONS
    ]



def get_signal_source_definition(source_type: str) -> dict[str, Any]:
    item = _definitions_by_type.get(source_type)
    if item is None:
        raise ValueError(f'不支持的信号源类型: {source_type}')
    return {
        'sourceType': item['sourceType'],
        'displayName': item['displayName'],
        'description': item['description'],
        'defaultParams': dict(item['defaultParams']),
        'paramSchema': [dict(field) for field in item['paramSchema']],
        'schemaVersion': item['schemaVersion'],
        'runtimeSupported': bool(item.get('runtimeSupported', False)),
    }
