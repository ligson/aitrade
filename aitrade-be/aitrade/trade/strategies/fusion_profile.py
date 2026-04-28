from __future__ import annotations

import copy
from typing import Any

from ...config.config_file import DEFAULT_BTC_SPOT_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG
from ...config.config_file import DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG
from ...web.exceptions import ValidationError

DEFAULT_SPOT_MULTI_SIGNAL_FUSION_PROFILE_CONFIG = {
    'klineNodes': [],
    'signalSourceNodes': [],
    'filters': {
        'min_available_nodes': 1,
        'allow_degraded': True,
        'min_confidence': 0.55,
        'buy_threshold': 0.55,
        'sell_threshold': 0.55,
    },
    'riskControls': {
        'default_risk_per_trade': 0.01,
        'shared_atr_period': 14,
        'shared_atr_stop_mult': 2.0,
        'shared_atr_trail_mult': 3.0,
    },
    'decisionPolicy': {
        'mode': 'weighted_score',
    },
}


def normalize_fusion_strategy_profile_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(raw_config or {})
    if _looks_like_structured_fusion_config(source):
        return _normalize_structured_fusion_config(source)
    return _convert_legacy_flat_config(source)



def summarize_fusion_strategy_profile_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_fusion_strategy_profile_config(config)
    kline_nodes = [item for item in normalized['klineNodes'] if bool(item.get('enabled', True))]
    signal_nodes = [item for item in normalized['signalSourceNodes'] if bool(item.get('enabled', True))]
    requires_1h = any(bool(item.get('requires_1h_timeframe')) for item in kline_nodes)
    return {
        'klineNodeCount': len(kline_nodes),
        'signalSourceNodeCount': len(signal_nodes),
        'minAvailableNodes': int(normalized['filters']['min_available_nodes']),
        'allowDegraded': bool(normalized['filters']['allow_degraded']),
        'decisionMode': str(normalized['decisionPolicy'].get('mode') or 'weighted_score'),
        'requires1hTimeframe': requires_1h,
    }



def build_fusion_runtime_params(
    profile_config: dict[str, Any],
    kline_node_snapshots: list[dict[str, Any]],
    signal_source_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = normalize_fusion_strategy_profile_config(profile_config)
    runtime_params = dict(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG)
    filters = dict(normalized.get('filters') or {})
    risk_controls = dict(normalized.get('riskControls') or {})
    decision_policy = dict(normalized.get('decisionPolicy') or {})
    runtime_params.update({
        'klineNodes': copy.deepcopy(kline_node_snapshots),
        'signalSourceNodes': copy.deepcopy(signal_source_snapshots),
        'filters': copy.deepcopy(filters),
        'riskControls': copy.deepcopy(risk_controls),
        'decisionPolicy': copy.deepcopy(decision_policy),
        'min_enabled_nodes': int(filters.get('min_available_nodes', 1) or 1),
        'allow_degraded': bool(filters.get('allow_degraded', True)),
        'min_confidence': float(filters.get('min_confidence', 0.55) or 0.55),
        'buy_threshold': float(filters.get('buy_threshold', 0.55) or 0.55),
        'sell_threshold': float(filters.get('sell_threshold', 0.55) or 0.55),
        'default_risk_per_trade': float(risk_controls.get('default_risk_per_trade', 0.01) or 0.01),
        'shared_atr_period': int(risk_controls.get('shared_atr_period', 14) or 14),
        'shared_atr_stop_mult': float(risk_controls.get('shared_atr_stop_mult', 2.0) or 2.0),
        'shared_atr_trail_mult': float(risk_controls.get('shared_atr_trail_mult', 3.0) or 3.0),
    })

    technical_node = next(
        (item for item in kline_node_snapshots if bool(item.get('enabled', True)) and item.get('nodeType') == 'builtin_technical'),
        None,
    )
    breakout_node = next(
        (item for item in kline_node_snapshots if bool(item.get('enabled', True)) and item.get('strategyType') == 'btc_spot_breakout'),
        None,
    )
    trend_node = next(
        (item for item in kline_node_snapshots if bool(item.get('enabled', True)) and item.get('strategyType') == 'btc_spot_trend_breakout'),
        None,
    )
    trade_flow_node = next(
        (item for item in signal_source_snapshots if bool(item.get('enabled', True)) and item.get('sourceType') == 'trade_flow'),
        None,
    )

    runtime_params['enable_trade_flow_node'] = trade_flow_node is not None
    runtime_params['trade_flow_weight'] = float((trade_flow_node or {}).get('weight', DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG['trade_flow_weight']))
    runtime_params['enable_kline_breakout_node'] = breakout_node is not None
    runtime_params['kline_breakout_weight'] = float((breakout_node or {}).get('weight', DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG['kline_breakout_weight']))
    runtime_params['enable_kline_trend_breakout_node'] = trend_node is not None
    runtime_params['kline_trend_breakout_weight'] = float((trend_node or {}).get('weight', DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG['kline_trend_breakout_weight']))
    runtime_params['enable_technical_node'] = technical_node is not None
    runtime_params['technical_weight'] = float((technical_node or {}).get('weight', DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG['technical_weight']))

    if technical_node is not None:
        runtime_params.update(dict(technical_node.get('params') or {}))
    if breakout_node is not None:
        breakout_params = dict(breakout_node.get('params') or {})
        runtime_params['kline_breakout_confirm_macd'] = bool(breakout_params.get('confirm_macd', runtime_params['kline_breakout_confirm_macd']))
        runtime_params['kline_breakout_confirm_volume'] = bool(breakout_params.get('confirm_volume', runtime_params['kline_breakout_confirm_volume']))
        runtime_params['kline_breakout_volume_multiplier'] = float(breakout_params.get('volume_multiplier', runtime_params['kline_breakout_volume_multiplier']))
        runtime_params['kline_breakout_breakout_buffer_bps'] = float(breakout_params.get('breakout_buffer_bps', runtime_params['kline_breakout_breakout_buffer_bps']))
    if trend_node is not None:
        trend_params = dict(trend_node.get('params') or {})
        runtime_params['kline_trend_breakout_adx_threshold'] = float(trend_params.get('adx_threshold', runtime_params['kline_trend_breakout_adx_threshold']))
        runtime_params['kline_trend_breakout_volume_multiplier'] = float(trend_params.get('volume_multiplier', runtime_params['kline_trend_breakout_volume_multiplier']))
    if trade_flow_node is not None:
        trade_flow_thresholds = dict(trade_flow_node.get('thresholds') or {})
        runtime_params['trade_flow_buy_ratio_threshold'] = float(trade_flow_thresholds.get('buy_ratio_threshold', runtime_params['trade_flow_buy_ratio_threshold']))
        runtime_params['trade_flow_sell_ratio_threshold'] = float(trade_flow_thresholds.get('sell_ratio_threshold', runtime_params['trade_flow_sell_ratio_threshold']))
        runtime_params['trade_flow_imbalance_threshold'] = float(trade_flow_thresholds.get('imbalance_threshold', runtime_params['trade_flow_imbalance_threshold']))
    return runtime_params



def _looks_like_structured_fusion_config(source: dict[str, Any]) -> bool:
    return any(key in source for key in ('klineNodes', 'signalSourceNodes', 'filters', 'riskControls', 'decisionPolicy'))



def _normalize_structured_fusion_config(source: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_PROFILE_CONFIG)

    kline_nodes = source.get('klineNodes') or []
    if not isinstance(kline_nodes, list):
        raise ValidationError('融合策略 klineNodes 必须是数组')
    normalized['klineNodes'] = [_normalize_kline_node(item) for item in kline_nodes]

    signal_source_nodes = source.get('signalSourceNodes') or []
    if not isinstance(signal_source_nodes, list):
        raise ValidationError('融合策略 signalSourceNodes 必须是数组')
    normalized['signalSourceNodes'] = [_normalize_signal_source_node(item) for item in signal_source_nodes]

    filters = dict(source.get('filters') or {})
    normalized['filters'].update({
        'min_available_nodes': _normalize_positive_int(filters.get('min_available_nodes', normalized['filters']['min_available_nodes']), 'filters.min_available_nodes'),
        'allow_degraded': _normalize_bool(filters.get('allow_degraded', normalized['filters']['allow_degraded']), 'filters.allow_degraded'),
        'min_confidence': _normalize_probability(filters.get('min_confidence', normalized['filters']['min_confidence']), 'filters.min_confidence'),
        'buy_threshold': _normalize_probability(filters.get('buy_threshold', normalized['filters']['buy_threshold']), 'filters.buy_threshold'),
        'sell_threshold': _normalize_probability(filters.get('sell_threshold', normalized['filters']['sell_threshold']), 'filters.sell_threshold'),
    })

    risk_controls = dict(source.get('riskControls') or {})
    normalized['riskControls'].update({
        'default_risk_per_trade': _normalize_probability(risk_controls.get('default_risk_per_trade', normalized['riskControls']['default_risk_per_trade']), 'riskControls.default_risk_per_trade', allow_zero=False),
        'shared_atr_period': _normalize_positive_int(risk_controls.get('shared_atr_period', normalized['riskControls']['shared_atr_period']), 'riskControls.shared_atr_period'),
        'shared_atr_stop_mult': _normalize_positive_number(risk_controls.get('shared_atr_stop_mult', normalized['riskControls']['shared_atr_stop_mult']), 'riskControls.shared_atr_stop_mult'),
        'shared_atr_trail_mult': _normalize_positive_number(risk_controls.get('shared_atr_trail_mult', normalized['riskControls']['shared_atr_trail_mult']), 'riskControls.shared_atr_trail_mult'),
    })

    decision_policy = dict(source.get('decisionPolicy') or {})
    mode = str(decision_policy.get('mode') or normalized['decisionPolicy']['mode']).strip() or 'weighted_score'
    if mode != 'weighted_score':
        raise ValidationError('decisionPolicy.mode 当前仅支持 weighted_score')
    normalized['decisionPolicy']['mode'] = mode

    enabled_node_count = sum(1 for item in normalized['klineNodes'] if bool(item.get('enabled', True))) + sum(
        1 for item in normalized['signalSourceNodes'] if bool(item.get('enabled', True))
    )
    if enabled_node_count <= 0:
        raise ValidationError('融合策略至少需要启用一个 K 线节点或信号源节点')
    if normalized['filters']['min_available_nodes'] > enabled_node_count:
        raise ValidationError('filters.min_available_nodes 不能大于已启用节点数')
    return normalized



def _convert_legacy_flat_config(source: dict[str, Any]) -> dict[str, Any]:
    legacy = dict(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG)
    legacy_aliases = {
        'enable_technical_signal': 'enable_technical_node',
        'enable_trade_flow_signal': 'enable_trade_flow_node',
        'min_enabled_sources': 'min_enabled_nodes',
        'atr_period': 'shared_atr_period',
        'atr_stop_mult': 'shared_atr_stop_mult',
        'atr_trail_mult': 'shared_atr_trail_mult',
    }
    for legacy_key, new_key in legacy_aliases.items():
        if legacy_key in source and new_key not in source:
            source[new_key] = source[legacy_key]
        source.pop(legacy_key, None)
    legacy.update(source)

    normalized = copy.deepcopy(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_PROFILE_CONFIG)
    if bool(legacy.get('enable_technical_node', True)):
        normalized['klineNodes'].append({
            'nodeType': 'builtin_technical',
            'strategyProfileId': None,
            'strategyType': 'builtin_technical',
            'name': '兼容技术面节点',
            'enabled': True,
            'weight': float(legacy.get('technical_weight', 0.6)),
            'params': {
                'technical_ema_period': int(legacy.get('technical_ema_period', 55)),
                'technical_breakout_lookback': int(legacy.get('technical_breakout_lookback', 20)),
                'technical_rsi_buy_max': float(legacy.get('technical_rsi_buy_max', 68)),
                'technical_rsi_sell_min': float(legacy.get('technical_rsi_sell_min', 52)),
                'technical_require_macd': bool(legacy.get('technical_require_macd', True)),
            },
            'requires_1h_timeframe': False,
        })
    if bool(legacy.get('enable_kline_breakout_node', False)):
        normalized['klineNodes'].append({
            'nodeType': 'strategy_profile',
            'strategyProfileId': None,
            'strategyType': 'btc_spot_breakout',
            'name': '兼容突破节点',
            'enabled': True,
            'weight': float(legacy.get('kline_breakout_weight', 0.5)),
            'params': {
                **dict(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG),
                'confirm_macd': bool(legacy.get('kline_breakout_confirm_macd', True)),
                'confirm_volume': bool(legacy.get('kline_breakout_confirm_volume', True)),
                'volume_multiplier': float(legacy.get('kline_breakout_volume_multiplier', 1.1)),
                'breakout_buffer_bps': float(legacy.get('kline_breakout_breakout_buffer_bps', 10)),
            },
            'requires_1h_timeframe': False,
        })
    if bool(legacy.get('enable_kline_trend_breakout_node', False)):
        normalized['klineNodes'].append({
            'nodeType': 'strategy_profile',
            'strategyProfileId': None,
            'strategyType': 'btc_spot_trend_breakout',
            'name': '兼容趋势突破节点',
            'enabled': True,
            'weight': float(legacy.get('kline_trend_breakout_weight', 0.5)),
            'params': {
                **dict(DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG),
                'adx_threshold': float(legacy.get('kline_trend_breakout_adx_threshold', 25)),
                'volume_multiplier': float(legacy.get('kline_trend_breakout_volume_multiplier', 1.0)),
            },
            'requires_1h_timeframe': True,
        })
    if bool(legacy.get('enable_trade_flow_node', True)):
        normalized['signalSourceNodes'].append({
            'signalSourceProfileId': None,
            'sourceType': 'trade_flow',
            'name': '兼容成交流节点',
            'enabled': True,
            'required': not bool(legacy.get('allow_degraded', True)),
            'weight': float(legacy.get('trade_flow_weight', 0.4)),
            'thresholds': {
                'buy_ratio_threshold': float(legacy.get('trade_flow_buy_ratio_threshold', 0.55)),
                'sell_ratio_threshold': float(legacy.get('trade_flow_sell_ratio_threshold', 0.45)),
                'imbalance_threshold': float(legacy.get('trade_flow_imbalance_threshold', 0.08)),
            },
            'params': {},
        })
    normalized['filters'].update({
        'min_available_nodes': int(legacy.get('min_enabled_nodes', 1)),
        'allow_degraded': bool(legacy.get('allow_degraded', True)),
        'min_confidence': float(legacy.get('min_confidence', 0.55)),
        'buy_threshold': float(legacy.get('buy_threshold', 0.55)),
        'sell_threshold': float(legacy.get('sell_threshold', 0.55)),
    })
    normalized['riskControls'].update({
        'default_risk_per_trade': float(legacy.get('default_risk_per_trade', 0.01)),
        'shared_atr_period': int(legacy.get('shared_atr_period', 14)),
        'shared_atr_stop_mult': float(legacy.get('shared_atr_stop_mult', 2.0)),
        'shared_atr_trail_mult': float(legacy.get('shared_atr_trail_mult', 3.0)),
    })
    return _normalize_structured_fusion_config(normalized)



def _normalize_kline_node(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError('融合策略 klineNodes 项必须是对象')
    node_type = str(value.get('nodeType') or 'strategy_profile').strip() or 'strategy_profile'
    if node_type not in {'strategy_profile', 'builtin_technical'}:
        raise ValidationError('融合策略 kline nodeType 仅支持 strategy_profile 或 builtin_technical')
    strategy_profile_id = value.get('strategyProfileId')
    if strategy_profile_id in {'', None}:
        normalized_strategy_profile_id = None
    else:
        normalized_strategy_profile_id = _normalize_positive_int(strategy_profile_id, 'klineNodes.strategyProfileId')
    strategy_type = str(value.get('strategyType') or '').strip()
    params = value.get('params') or {}
    if not isinstance(params, dict):
        raise ValidationError('融合策略 klineNodes.params 必须是对象')
    return {
        'nodeType': node_type,
        'strategyProfileId': normalized_strategy_profile_id,
        'strategyType': strategy_type,
        'name': str(value.get('name') or '').strip(),
        'enabled': _normalize_bool(value.get('enabled', True), 'klineNodes.enabled'),
        'weight': _normalize_probability(value.get('weight', 0.5), 'klineNodes.weight', allow_zero=False),
        'params': copy.deepcopy(params),
        'requires_1h_timeframe': bool(value.get('requires_1h_timeframe', False)),
    }



def _normalize_signal_source_node(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError('融合策略 signalSourceNodes 项必须是对象')
    signal_source_profile_id = value.get('signalSourceProfileId')
    if signal_source_profile_id in {'', None}:
        normalized_signal_source_profile_id = None
    else:
        normalized_signal_source_profile_id = _normalize_positive_int(signal_source_profile_id, 'signalSourceNodes.signalSourceProfileId')
    thresholds = value.get('thresholds') or {}
    if not isinstance(thresholds, dict):
        raise ValidationError('融合策略 signalSourceNodes.thresholds 必须是对象')
    params = value.get('params') or {}
    if not isinstance(params, dict):
        raise ValidationError('融合策略 signalSourceNodes.params 必须是对象')
    return {
        'signalSourceProfileId': normalized_signal_source_profile_id,
        'sourceType': str(value.get('sourceType') or '').strip(),
        'name': str(value.get('name') or '').strip(),
        'enabled': _normalize_bool(value.get('enabled', True), 'signalSourceNodes.enabled'),
        'required': _normalize_bool(value.get('required', False), 'signalSourceNodes.required'),
        'weight': _normalize_probability(value.get('weight', 0.4), 'signalSourceNodes.weight', allow_zero=False),
        'thresholds': {
            'buy_ratio_threshold': _normalize_probability(thresholds.get('buy_ratio_threshold', 0.55), 'signalSourceNodes.thresholds.buy_ratio_threshold', allow_zero=False),
            'sell_ratio_threshold': _normalize_probability(thresholds.get('sell_ratio_threshold', 0.45), 'signalSourceNodes.thresholds.sell_ratio_threshold', allow_zero=False),
            'imbalance_threshold': _normalize_probability(thresholds.get('imbalance_threshold', 0.08), 'signalSourceNodes.thresholds.imbalance_threshold', allow_zero=False),
        },
        'params': copy.deepcopy(params),
    }



def _normalize_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f'{label} 必须是布尔值')
    return value



def _normalize_positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'{label} 必须是正整数')
    normalized = int(value)
    if normalized <= 0:
        raise ValidationError(f'{label} 必须大于 0')
    return normalized



def _normalize_positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'{label} 必须是数字')
    normalized = float(value)
    if normalized <= 0:
        raise ValidationError(f'{label} 必须大于 0')
    return normalized



def _normalize_probability(value: Any, label: str, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f'{label} 必须是数字')
    normalized = float(value)
    if allow_zero:
        if normalized < 0 or normalized > 1:
            raise ValidationError(f'{label} 必须在 0 到 1 之间')
    else:
        if normalized <= 0 or normalized > 1:
            raise ValidationError(f'{label} 必须在 0 到 1 之间，且不能为 0')
    return normalized
