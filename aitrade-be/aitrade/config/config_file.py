import copy
import logging
import os
from typing import Any
from typing import Dict

import yaml

from .path_utils import build_managed_data_paths
from .path_utils import build_sqlite_database_url
from .path_utils import extract_sqlite_database_path
from .path_utils import infer_data_root_dir
from .path_utils import infer_data_root_dir_from_leaf_paths
from .path_utils import normalize_database_url
from .path_utils import normalize_filesystem_path
from .path_utils import resolve_backtest_data_dir
from .path_utils import resolve_data_root_dir
from .path_utils import resolve_default_backtest_data_dir
from .path_utils import resolve_default_data_root_dir
from .path_utils import resolve_default_freqtrade_user_data_dir
from .path_utils import resolve_default_log_dir
from .path_utils import resolve_default_sqlite_path
from .path_utils import resolve_freqtrade_user_data_dir
from .path_utils import resolve_log_dir
from .path_utils import resolve_sqlite_path


DEFAULT_GPT_STRATEGY_CONFIG = {
    'min_confidence': 0.7,
}

DEFAULT_BTC_SPOT_BREAKOUT_CONFIG = {
    'donchian_entry': 20,
    'donchian_exit': 10,
    'ema_period': 96,
    'ema_slope_lookback': 4,
    'atr_period': 14,
    'atr_stop_mult': 2.5,
    'atr_trail_mult': 3.0,
    'breakout_buffer_bps': 10,
    'confirm_macd': True,
    'confirm_volume': True,
    'volume_ma_period': 20,
    'volume_multiplier': 1.1,
    'default_risk_per_trade': 0.01,
}

DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG = {
    'ema_fast_period': 20,
    'ema_slow_period': 50,
    'adx_period': 14,
    'adx_threshold': 25,
    'breakout_lookback': 20,
    'volume_ma_period': 20,
    'volume_multiplier': 1.0,
    'atr_period': 14,
    'atr_stop_mult': 2.0,
    'atr_trail_mult': 3.0,
    'default_risk_per_trade': 0.01,
}

DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG = {
    'enable_technical_node': True,
    'enable_trade_flow_node': True,
    'enable_kline_breakout_node': False,
    'enable_kline_trend_breakout_node': False,
    'technical_weight': 0.6,
    'trade_flow_weight': 0.4,
    'kline_breakout_weight': 0.5,
    'kline_trend_breakout_weight': 0.5,
    'min_enabled_nodes': 1,
    'allow_degraded': True,
    'min_confidence': 0.55,
    'buy_threshold': 0.55,
    'sell_threshold': 0.55,
    'default_risk_per_trade': 0.01,
    'shared_atr_period': 14,
    'shared_atr_stop_mult': 2.0,
    'shared_atr_trail_mult': 3.0,
    'technical_ema_period': 55,
    'technical_breakout_lookback': 20,
    'technical_rsi_buy_max': 68,
    'technical_rsi_sell_min': 52,
    'technical_require_macd': True,
    'trade_flow_buy_ratio_threshold': 0.55,
    'trade_flow_sell_ratio_threshold': 0.45,
    'trade_flow_imbalance_threshold': 0.08,
    'kline_breakout_confirm_macd': True,
    'kline_breakout_confirm_volume': True,
    'kline_breakout_volume_multiplier': 1.1,
    'kline_breakout_breakout_buffer_bps': 10,
    'kline_trend_breakout_adx_threshold': 25,
    'kline_trend_breakout_volume_multiplier': 1.0,
}

DEFAULT_TRADE_MARKET_FEEDS_CONFIG = {
    'trade_flow': {
        'enabled': True,
        'freshness_seconds': 120,
        'lookback_trades': 200,
    },
}

DEFAULT_TRADE_PERSISTENCE_CONFIG = {
    'enabled': True,
    'database_url': build_sqlite_database_url(resolve_default_sqlite_path()),
    'persist_position': True,
    'restore_position_on_startup': False,
}

DEFAULT_TRADE_TASK_DEFAULTS_CONFIG = {
    'fee_rate': 0.0,
    'slippage_rate': 0.0,
    'daily_loss_stop_enabled': False,
    'daily_loss_stop_threshold': 100.0,
}

DEFAULT_TRADE_EXECUTION_CONFIG = dict(DEFAULT_TRADE_TASK_DEFAULTS_CONFIG)

TRADE_MODES = {'live', 'sandbox', 'paper'}
DEFAULT_PAPER_BALANCE = 10000.0

DEFAULT_WEB_INIT_ADMIN_CONFIG = {
    'enabled': True,
    'username': 'admin',
    'password': 'admin123456',
    'email': 'admin@example.com',
    'nickname': '管理员',
    'remark': '系统初始化管理员',
}

DEFAULT_WEB_CONFIG = {
    'host': '127.0.0.1',
    'port': 18080,
    'debug': True,
    'show_trace': True,
    'jwt_secret': 'change-me-in-production',
    'jwt_expire_minutes': 720,
    'captcha_expire_seconds': 300,
    'cors_allow_origins': ['http://127.0.0.1:5173', 'http://localhost:5173'],
    'init_admin': DEFAULT_WEB_INIT_ADMIN_CONFIG,
}

DEFAULT_BACKTEST_CONFIG = {
    'data_dir': resolve_default_backtest_data_dir(),
    'user_data_dir': resolve_default_freqtrade_user_data_dir(),
    'supported_symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
    'supported_timeframes': ['5m', '15m', '30m', '1h', '4h', '1d'],
    'default_symbol': 'BTC/USDT',
    'default_timeframe': '15m',
    'download_timerange': '20180101-',
    'freqtrade_bin': 'freqtrade',
    'data_format_ohlcv': 'jsongz',
    'export_archive_format': 'zip',
}


class ConfigValidationError(ValueError):
    pass



def load_config(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except FileNotFoundError as exc:
        raise ConfigValidationError(f"配置文件不存在：{os.path.abspath(config_file)}") from exc
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"config.yaml YAML 格式错误：{exc}") from exc



def merge_config(defaults, overrides):
    merged = copy.deepcopy(defaults)
    if overrides:
        merged.update(overrides)
    return merged



def _require_mapping(value, path):
    if not isinstance(value, dict):
        raise ConfigValidationError(f"配置项 {path} 必须是对象/字典")
    return value



def _require_non_empty_string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"配置项 {path} 必须是非空字符串")
    return value.strip()



def _require_bool(value, path):
    if not isinstance(value, bool):
        raise ConfigValidationError(f"配置项 {path} 必须是布尔值 true 或 false")
    return value



def _require_positive_int(value, path):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigValidationError(f"配置项 {path} 必须是大于 0 的整数")
    return value



def _require_positive_number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigValidationError(f"配置项 {path} 必须是大于 0 的数字")
    return value


def _require_non_negative_number(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigValidationError(f"配置项 {path} 必须是大于等于 0 的数字")
    return value


def _require_string_list(value, path):
    if not isinstance(value, list):
        raise ConfigValidationError(f"配置项 {path} 必须是字符串数组")
    items = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigValidationError(f"配置项 {path}[{index}] 必须是非空字符串")
        items.append(item.strip())
    return items


def _normalize_trade_mode(trade_cfg, path_prefix='app.trade'):
    trade_mode = trade_cfg.get('trade_mode')
    if trade_mode is not None:
        normalized = _require_non_empty_string(trade_mode, f'{path_prefix}.trade_mode').lower()
        if normalized not in TRADE_MODES:
            raise ConfigValidationError('配置项 app.trade.trade_mode 只支持 live、sandbox 或 paper')
        return normalized

    sandbox_trade = _require_bool(trade_cfg.get('sandbox_trade', True), f'{path_prefix}.sandbox_trade')
    logging.info('未显式提供 app.trade.trade_mode，继续兼容使用 sandbox_trade=%s', sandbox_trade)
    return 'sandbox' if sandbox_trade else 'live'


def normalize_spot_multi_signal_fusion_config(raw_config: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(raw_config or {})
    normalized = dict(DEFAULT_SPOT_MULTI_SIGNAL_FUSION_CONFIG)
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
            logging.info('检测到现货多源融合策略旧字段 %s，自动映射到 %s', legacy_key, new_key)
            source[new_key] = source[legacy_key]
        source.pop(legacy_key, None)
    normalized.update(source)
    return normalized


class Config:
    @classmethod
    def from_yaml(cls, config_file: str, mode: str = 'web') -> 'Config':
        return cls(config_file, mode=mode)

    @classmethod
    def from_dict(cls, config_data: dict[str, Any], mode: str = 'web') -> 'Config':
        return cls(copy.deepcopy(config_data), mode=mode)

    def __init__(self, config_source, mode: str = 'bot'):
        self.config_path: str | None = None
        if isinstance(config_source, dict):
            self.config = copy.deepcopy(config_source)
            logging.debug('从内存对象初始化配置，mode=%s', mode)
        else:
            config_file = str(config_source)
            self.config_path = os.path.abspath(config_file)
            if os.path.exists(config_file):
                logging.info("配置文件存在，绝对路径：%s", self.config_path)
            else:
                logging.info("%s配置文件不存在", config_file)
            self.config = load_config(config_file)
        if mode not in {'web', 'task_runtime'}:
            raise ConfigValidationError("Config mode 只支持 web 或 task_runtime")
        self.mode = mode

        if not isinstance(self.config, dict):
            raise ConfigValidationError("config.yaml 顶层结构必须是对象，且至少包含 app 配置")

        app_cfg = _require_mapping(self.config.get('app'), 'app')
        raw_data_root_dir = app_cfg.get('data_root_dir')
        self.data_root_mode = 'managed'
        self.data_root_dir = resolve_default_data_root_dir()
        if raw_data_root_dir is not None:
            self.data_root_dir = resolve_data_root_dir(_require_non_empty_string(raw_data_root_dir, 'app.data_root_dir'))
            app_cfg['data_root_dir'] = self.data_root_dir

        # Web 服务自身启动只要求部署级/系统级配置；
        # 交易任务真正运行前，仍要求提供完整 AI 配置。
        gpt_raw = app_cfg.get('gpt')
        if self.mode == 'task_runtime':
            gpt_cfg = _require_mapping(gpt_raw, 'app.gpt')
        elif gpt_raw is None:
            logging.debug('Web 模式未在 config.yaml 中提供 app.gpt，后续由系统设置补齐可编辑 AI 参数')
            gpt_cfg = {}
        else:
            gpt_cfg = _require_mapping(gpt_raw, 'app.gpt')
        self.gpt_provider = _require_non_empty_string(gpt_cfg.get('provider', 'deepseek'), 'app.gpt.provider')
        if self.gpt_provider not in {'deepseek', 'openai'}:
            raise ConfigValidationError("配置项 app.gpt.provider 只支持 deepseek 或 openai")
        gpt_api_key = str(gpt_cfg.get('api_key') or '').strip()
        if self.mode == 'task_runtime':
            self.gpt_api_key = _require_non_empty_string(gpt_api_key, 'app.gpt.api_key')
        else:
            self.gpt_api_key = gpt_api_key
        self.gpt_model = _require_non_empty_string(gpt_cfg.get('model', 'deepseek-chat'), 'app.gpt.model')
        gpt_base_url = gpt_cfg.get('base_url')
        if gpt_base_url is None:
            self.gpt_base_url = ''
        elif not isinstance(gpt_base_url, str):
            raise ConfigValidationError('配置项 app.gpt.base_url 必须是字符串')
        else:
            self.gpt_base_url = gpt_base_url.strip()

        http_client_cfg = _require_mapping(app_cfg.get('http_client'), 'app.http_client')
        self.proxy_enable = _require_bool(http_client_cfg.get('proxy_enable', False), 'app.http_client.proxy_enable')
        self.proxy_url = http_client_cfg.get('proxy_url')
        if self.proxy_enable:
            self.proxy_url = _require_non_empty_string(self.proxy_url, 'app.http_client.proxy_url')
        elif self.proxy_url is not None and not isinstance(self.proxy_url, str):
            raise ConfigValidationError("配置项 app.http_client.proxy_url 必须是字符串")

        exchange_raw = app_cfg.get('exchange')
        if self.mode == 'task_runtime':
            exchange_cfg = _require_mapping(exchange_raw, 'app.exchange')
        elif exchange_raw is None:
            logging.debug('Web 模式未在 config.yaml 中提供 app.exchange，后续可由用户交易所设置补齐')
            exchange_cfg = {}
        else:
            exchange_cfg = _require_mapping(exchange_raw, 'app.exchange')
        exchange_type = str(exchange_cfg.get('type') or '').strip().lower()
        if self.mode == 'task_runtime':
            self.exchange_type = _require_non_empty_string(exchange_type, 'app.exchange.type')
        else:
            self.exchange_type = exchange_type
        if self.exchange_type and self.exchange_type not in {'binance', 'okx'}:
            raise ConfigValidationError("配置项 app.exchange.type 只支持 binance 或 okx")
        exchange_api_key = str(exchange_cfg.get('api_key') or '').strip()
        exchange_api_secret = str(exchange_cfg.get('api_secret') or '').strip()
        if self.mode == 'task_runtime':
            self.exchange_api_key = _require_non_empty_string(exchange_api_key, 'app.exchange.api_key')
            self.exchange_api_secret = _require_non_empty_string(exchange_api_secret, 'app.exchange.api_secret')
        else:
            self.exchange_api_key = exchange_api_key
            self.exchange_api_secret = exchange_api_secret
        password = exchange_cfg.get('password', '')
        if password is None:
            password = ''
        if not isinstance(password, str):
            raise ConfigValidationError("配置项 app.exchange.password 必须是字符串")
        self.exchange_password = password
        if self.mode == 'task_runtime' and self.exchange_type == 'okx' and not self.exchange_password.strip():
            raise ConfigValidationError("使用 OKX 时，配置项 app.exchange.password 不能为空")

        trade_raw = app_cfg.get('trade')
        trade_cfg = _require_mapping(trade_raw, 'app.trade') if trade_raw is not None else {}
        has_trade_task_fields = any(key in trade_cfg for key in ('trade_mode', 'sandbox_trade', 'symbol', 'timeframe', 'limit', 'strategy'))
        # Web 服务自身启动不要求文件里提供完整任务级配置；
        # 真实交易任务运行前，必须具备完整的运行态参数。
        if self.mode == 'task_runtime' and not has_trade_task_fields:
            raise ConfigValidationError(
                '交易任务运行态要求在 app.trade 中提供任务级配置：trade_mode、symbol、timeframe、limit、strategy'
            )

        self.trade_mode = _normalize_trade_mode(trade_cfg)
        self.trade_sandbox_trade = self.trade_mode == 'sandbox'
        self.trade_paper_balance = float(_require_positive_number(trade_cfg.get('paper_balance', DEFAULT_PAPER_BALANCE), 'app.trade.paper_balance'))
        self.trade_symbol = _require_non_empty_string(trade_cfg.get('symbol', 'BTC/USDT'), 'app.trade.symbol')
        self.trade_timeframe = _require_positive_int(trade_cfg.get('timeframe', 15), 'app.trade.timeframe')
        self.trade_limit = _require_positive_int(trade_cfg.get('limit', 100), 'app.trade.limit')
        task_defaults_overrides = trade_cfg.get('task_defaults', {})
        if task_defaults_overrides is None:
            task_defaults_overrides = {}
        task_defaults_overrides = _require_mapping(task_defaults_overrides, 'app.trade.task_defaults')
        self.trade_task_defaults_config = merge_config(DEFAULT_TRADE_TASK_DEFAULTS_CONFIG, task_defaults_overrides)

        market_feeds_overrides = trade_cfg.get('market_feeds', {})
        if market_feeds_overrides is None:
            market_feeds_overrides = {}
        market_feeds_overrides = _require_mapping(market_feeds_overrides, 'app.trade.market_feeds')
        self.trade_market_feeds_config = copy.deepcopy(DEFAULT_TRADE_MARKET_FEEDS_CONFIG)
        trade_flow_feed_overrides = market_feeds_overrides.get('trade_flow', {})
        if trade_flow_feed_overrides is None:
            trade_flow_feed_overrides = {}
        trade_flow_feed_overrides = _require_mapping(trade_flow_feed_overrides, 'app.trade.market_feeds.trade_flow')
        self.trade_market_feeds_config['trade_flow'].update(trade_flow_feed_overrides)

        execution_overrides = trade_cfg.get('execution', {})
        if execution_overrides is None:
            execution_overrides = {}
        execution_overrides = _require_mapping(execution_overrides, 'app.trade.execution')
        self.trade_execution_config = merge_config(DEFAULT_TRADE_EXECUTION_CONFIG, execution_overrides)

        strategy_raw = trade_cfg.get('strategy')
        if strategy_raw is None:
            if self.mode == 'task_runtime':
                raise ConfigValidationError('交易任务运行态要求提供配置项 app.trade.strategy')
            strategy_cfg = {}
        else:
            strategy_cfg = _require_mapping(strategy_raw, 'app.trade.strategy')
        self.trade_strategy_type = _require_non_empty_string(strategy_cfg.get('type', 'gpt'), 'app.trade.strategy.type')
        if self.trade_strategy_type not in {'gpt', 'btc_spot_breakout', 'btc_spot_trend_breakout', 'spot_multi_signal_fusion'}:
            raise ConfigValidationError("配置项 app.trade.strategy.type 只支持 gpt、btc_spot_breakout、btc_spot_trend_breakout 或 spot_multi_signal_fusion")

        self.trade_strategy_gpt_config = merge_config(DEFAULT_GPT_STRATEGY_CONFIG, strategy_cfg.get('gpt', {}))
        self.trade_strategy_btc_spot_config = merge_config(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG, strategy_cfg.get('btc_spot_breakout', {}))
        self.trade_strategy_btc_spot_trend_breakout_config = merge_config(
            DEFAULT_BTC_SPOT_TREND_BREAKOUT_CONFIG,
            strategy_cfg.get('btc_spot_trend_breakout', {}),
        )
        self.trade_strategy_spot_multi_signal_fusion_config = normalize_spot_multi_signal_fusion_config(
            strategy_cfg.get('spot_multi_signal_fusion', {}),
        )

        persistence_overrides = trade_cfg.get('persistence', {})
        if persistence_overrides is None:
            persistence_overrides = {}
        persistence_overrides = _require_mapping(persistence_overrides, 'app.trade.persistence')
        self.trade_persistence_config = merge_config(DEFAULT_TRADE_PERSISTENCE_CONFIG, persistence_overrides)

        _require_bool(self.trade_persistence_config.get('enabled'), 'app.trade.persistence.enabled')
        if raw_data_root_dir is not None:
            self.trade_persistence_config['database_url'] = build_sqlite_database_url(resolve_sqlite_path(self.data_root_dir))
            persistence_overrides.pop('sqlite_path', None)
        else:
            database_url = persistence_overrides.get('database_url')
            # trade.persistence 仍属于部署期配置边界，真实数据库连接地址只从文件配置或部署设置写回的 config.yaml 读取。
            # sqlite_path 仅用于兼容旧配置，新的配置文件统一使用 database_url。
            if database_url is None and persistence_overrides.get('sqlite_path') is not None:
                logging.info('检测到旧字段 app.trade.persistence.sqlite_path，自动转换为 database_url 使用')
                sqlite_path = _require_non_empty_string(
                    persistence_overrides.get('sqlite_path'),
                    'app.trade.persistence.sqlite_path',
                )
                database_url = build_sqlite_database_url(sqlite_path)
            self.trade_persistence_config['database_url'] = normalize_database_url(_require_non_empty_string(
                database_url or self.trade_persistence_config.get('database_url'),
                'app.trade.persistence.database_url',
            ))
            if persistence_overrides.get('sqlite_path') is not None:
                self.trade_persistence_config['sqlite_path'] = _require_non_empty_string(
                    persistence_overrides.get('sqlite_path'),
                    'app.trade.persistence.sqlite_path',
                )
        persistence_overrides['database_url'] = self.trade_persistence_config['database_url']
        trade_cfg['persistence'] = persistence_overrides
        _require_bool(self.trade_persistence_config.get('persist_position'), 'app.trade.persistence.persist_position')
        _require_bool(
            self.trade_persistence_config.get('restore_position_on_startup'),
            'app.trade.persistence.restore_position_on_startup',
        )

        for key in ('fee_rate', 'slippage_rate', 'daily_loss_stop_threshold'):
            _require_non_negative_number(self.trade_task_defaults_config.get(key), f'app.trade.task_defaults.{key}')
            _require_non_negative_number(self.trade_execution_config.get(key), f'app.trade.execution.{key}')
        for key in ('daily_loss_stop_enabled',):
            _require_bool(self.trade_task_defaults_config.get(key), f'app.trade.task_defaults.{key}')
            _require_bool(self.trade_execution_config.get(key), f'app.trade.execution.{key}')
        if self.trade_task_defaults_config['daily_loss_stop_enabled'] and float(self.trade_task_defaults_config['daily_loss_stop_threshold']) <= 0:
            raise ConfigValidationError('配置项 app.trade.task_defaults.daily_loss_stop_threshold 必须大于 0')
        if self.trade_execution_config['daily_loss_stop_enabled'] and float(self.trade_execution_config['daily_loss_stop_threshold']) <= 0:
            raise ConfigValidationError('配置项 app.trade.execution.daily_loss_stop_threshold 必须大于 0')

        trade_flow_feed_cfg = dict(self.trade_market_feeds_config.get('trade_flow') or {})
        _require_bool(trade_flow_feed_cfg.get('enabled'), 'app.trade.market_feeds.trade_flow.enabled')
        _require_positive_int(trade_flow_feed_cfg.get('freshness_seconds'), 'app.trade.market_feeds.trade_flow.freshness_seconds')
        _require_positive_int(trade_flow_feed_cfg.get('lookback_trades'), 'app.trade.market_feeds.trade_flow.lookback_trades')

        web_overrides = app_cfg.get('web', {})
        if web_overrides is None:
            web_overrides = {}
        web_overrides = _require_mapping(web_overrides, 'app.web')
        self.web_config = merge_config(DEFAULT_WEB_CONFIG, web_overrides)
        self.web_host = _require_non_empty_string(self.web_config.get('host'), 'app.web.host')
        self.web_port = _require_positive_int(self.web_config.get('port'), 'app.web.port')
        self.web_debug = _require_bool(self.web_config.get('debug'), 'app.web.debug')
        self.web_show_trace = _require_bool(self.web_config.get('show_trace'), 'app.web.show_trace')
        self.web_cors_allow_origins = _require_string_list(
            self.web_config.get('cors_allow_origins', []),
            'app.web.cors_allow_origins',
        )
        self.web_jwt_secret = _require_non_empty_string(self.web_config.get('jwt_secret'), 'app.web.jwt_secret')
        self.web_jwt_expire_minutes = _require_positive_int(
            self.web_config.get('jwt_expire_minutes'),
            'app.web.jwt_expire_minutes',
        )
        self.web_captcha_expire_seconds = _require_positive_int(
            self.web_config.get('captcha_expire_seconds'),
            'app.web.captcha_expire_seconds',
        )
        init_admin_overrides = self.web_config.get('init_admin', {})
        if init_admin_overrides is None:
            init_admin_overrides = {}
        init_admin_overrides = _require_mapping(init_admin_overrides, 'app.web.init_admin')
        self.web_init_admin_config = merge_config(DEFAULT_WEB_INIT_ADMIN_CONFIG, init_admin_overrides)
        _require_bool(self.web_init_admin_config.get('enabled'), 'app.web.init_admin.enabled')
        self.web_init_admin_config['username'] = _require_non_empty_string(
            self.web_init_admin_config.get('username'),
            'app.web.init_admin.username',
        )
        self.web_init_admin_config['password'] = _require_non_empty_string(
            self.web_init_admin_config.get('password'),
            'app.web.init_admin.password',
        )
        self.web_init_admin_config['email'] = _require_non_empty_string(
            self.web_init_admin_config.get('email'),
            'app.web.init_admin.email',
        )
        self.web_init_admin_config['nickname'] = _require_non_empty_string(
            self.web_init_admin_config.get('nickname'),
            'app.web.init_admin.nickname',
        )
        remark = self.web_init_admin_config.get('remark', '')
        if remark is None:
            remark = ''
        if not isinstance(remark, str):
            raise ConfigValidationError('配置项 app.web.init_admin.remark 必须是字符串')
        self.web_init_admin_config['remark'] = remark

        # Web 页面保存的业务默认参数与部署设置分开管理；目录路径和外部命令仍然以文件配置为准。
        backtest_overrides = app_cfg.get('backtest', {})
        if backtest_overrides is None:
            backtest_overrides = {}
        backtest_overrides = _require_mapping(backtest_overrides, 'app.backtest')
        self.backtest_config = merge_config(DEFAULT_BACKTEST_CONFIG, backtest_overrides)
        if raw_data_root_dir is not None:
            managed_paths = build_managed_data_paths(self.data_root_dir)
            self.backtest_config['data_dir'] = managed_paths['backtestDataDir']
            self.backtest_config['user_data_dir'] = managed_paths['freqtradeUserDataDir']
            self.log_dir = managed_paths['appLogDir']
            self.data_root_mode = 'managed'
        else:
            self.backtest_config['data_dir'] = normalize_filesystem_path(_require_non_empty_string(
                self.backtest_config.get('data_dir'),
                'app.backtest.data_dir',
            ))
            self.backtest_config['user_data_dir'] = normalize_filesystem_path(_require_non_empty_string(
                self.backtest_config.get('user_data_dir'),
                'app.backtest.user_data_dir',
            ))
            log_dir_value = app_cfg.get('log_dir', resolve_default_log_dir())
            self.log_dir = normalize_filesystem_path(_require_non_empty_string(log_dir_value, 'app.log_dir'))
            inferred_data_root_dir = infer_data_root_dir(
                self.trade_persistence_config['database_url'],
                self.log_dir,
                self.backtest_config['data_dir'],
                self.backtest_config['user_data_dir'],
            )
            if inferred_data_root_dir is not None:
                self.data_root_dir = inferred_data_root_dir
                self.data_root_mode = 'legacy_inferred'
            elif extract_sqlite_database_path(self.trade_persistence_config['database_url']) is None:
                inferred_leaf_root = infer_data_root_dir_from_leaf_paths(
                    self.log_dir,
                    self.backtest_config['data_dir'],
                    self.backtest_config['user_data_dir'],
                )
                self.data_root_dir = inferred_leaf_root or resolve_default_data_root_dir()
                self.data_root_mode = 'external_database'
            else:
                inferred_leaf_root = infer_data_root_dir_from_leaf_paths(
                    self.log_dir,
                    self.backtest_config['data_dir'],
                    self.backtest_config['user_data_dir'],
                )
                sqlite_path = extract_sqlite_database_path(self.trade_persistence_config['database_url'])
                self.data_root_dir = inferred_leaf_root or str(os.path.dirname(sqlite_path))
                self.data_root_mode = 'legacy_split'
        if raw_data_root_dir is not None:
            app_cfg['data_root_dir'] = self.data_root_dir
        app_cfg['log_dir'] = self.log_dir
        backtest_overrides['data_dir'] = self.backtest_config['data_dir']
        backtest_overrides['user_data_dir'] = self.backtest_config['user_data_dir']
        app_cfg['backtest'] = backtest_overrides
        self.managed_data_paths = build_managed_data_paths(self.data_root_dir)
        self.backtest_config['supported_symbols'] = _require_string_list(
            self.backtest_config.get('supported_symbols'),
            'app.backtest.supported_symbols',
        )
        self.backtest_config['supported_timeframes'] = _require_string_list(
            self.backtest_config.get('supported_timeframes'),
            'app.backtest.supported_timeframes',
        )
        self.backtest_config['default_symbol'] = _require_non_empty_string(
            self.backtest_config.get('default_symbol'),
            'app.backtest.default_symbol',
        )
        if self.backtest_config['default_symbol'] not in self.backtest_config['supported_symbols']:
            raise ConfigValidationError('配置项 app.backtest.default_symbol 必须包含在 app.backtest.supported_symbols 中')
        self.backtest_config['default_timeframe'] = _require_non_empty_string(
            self.backtest_config.get('default_timeframe'),
            'app.backtest.default_timeframe',
        )
        if self.backtest_config['default_timeframe'] not in self.backtest_config['supported_timeframes']:
            raise ConfigValidationError('配置项 app.backtest.default_timeframe 必须包含在 app.backtest.supported_timeframes 中')
        self.backtest_config['download_timerange'] = _require_non_empty_string(
            self.backtest_config.get('download_timerange'),
            'app.backtest.download_timerange',
        )
        self.backtest_config['freqtrade_bin'] = _require_non_empty_string(
            self.backtest_config.get('freqtrade_bin'),
            'app.backtest.freqtrade_bin',
        )
        self.backtest_config['data_format_ohlcv'] = _require_non_empty_string(
            self.backtest_config.get('data_format_ohlcv'),
            'app.backtest.data_format_ohlcv',
        )
        if self.backtest_config['data_format_ohlcv'] not in {'json', 'jsongz'}:
            raise ConfigValidationError('配置项 app.backtest.data_format_ohlcv 只支持 json 或 jsongz')
        self.backtest_config['export_archive_format'] = _require_non_empty_string(
            self.backtest_config.get('export_archive_format'),
            'app.backtest.export_archive_format',
        )
        if self.backtest_config['export_archive_format'] != 'zip':
            raise ConfigValidationError('配置项 app.backtest.export_archive_format 当前只支持 zip')

        _require_positive_number(
            self.trade_strategy_gpt_config.get('min_confidence'),
            'app.trade.strategy.gpt.min_confidence',
        )

        btc_spot_cfg = self.trade_strategy_btc_spot_config
        for key in ('donchian_entry', 'donchian_exit', 'ema_period', 'ema_slope_lookback', 'atr_period', 'volume_ma_period'):
            _require_positive_int(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')
        for key in ('atr_stop_mult', 'atr_trail_mult', 'breakout_buffer_bps', 'volume_multiplier', 'default_risk_per_trade'):
            _require_positive_number(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')
        for key in ('confirm_macd', 'confirm_volume'):
            _require_bool(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')

        btc_spot_trend_cfg = self.trade_strategy_btc_spot_trend_breakout_config
        for key in ('ema_fast_period', 'ema_slow_period', 'adx_period', 'breakout_lookback', 'volume_ma_period', 'atr_period'):
            _require_positive_int(btc_spot_trend_cfg.get(key), f'app.trade.strategy.btc_spot_trend_breakout.{key}')
        for key in ('adx_threshold', 'volume_multiplier', 'atr_stop_mult', 'atr_trail_mult', 'default_risk_per_trade'):
            _require_positive_number(btc_spot_trend_cfg.get(key), f'app.trade.strategy.btc_spot_trend_breakout.{key}')
        if int(btc_spot_trend_cfg.get('ema_fast_period')) >= int(btc_spot_trend_cfg.get('ema_slow_period')):
            raise ConfigValidationError('配置项 app.trade.strategy.btc_spot_trend_breakout.ema_fast_period 必须小于 ema_slow_period')

        fusion_cfg = self.trade_strategy_spot_multi_signal_fusion_config
        for key in ('technical_ema_period', 'technical_breakout_lookback', 'min_enabled_nodes', 'shared_atr_period'):
            _require_positive_int(fusion_cfg.get(key), f'app.trade.strategy.spot_multi_signal_fusion.{key}')
        for key in (
            'technical_weight',
            'trade_flow_weight',
            'kline_breakout_weight',
            'kline_trend_breakout_weight',
            'min_confidence',
            'buy_threshold',
            'sell_threshold',
            'technical_rsi_buy_max',
            'technical_rsi_sell_min',
            'trade_flow_buy_ratio_threshold',
            'trade_flow_sell_ratio_threshold',
            'trade_flow_imbalance_threshold',
            'shared_atr_stop_mult',
            'shared_atr_trail_mult',
            'default_risk_per_trade',
            'kline_breakout_volume_multiplier',
            'kline_breakout_breakout_buffer_bps',
            'kline_trend_breakout_adx_threshold',
            'kline_trend_breakout_volume_multiplier',
        ):
            _require_positive_number(fusion_cfg.get(key), f'app.trade.strategy.spot_multi_signal_fusion.{key}')
        for key in (
            'enable_technical_node',
            'enable_trade_flow_node',
            'enable_kline_breakout_node',
            'enable_kline_trend_breakout_node',
            'allow_degraded',
            'technical_require_macd',
            'kline_breakout_confirm_macd',
            'kline_breakout_confirm_volume',
        ):
            _require_bool(fusion_cfg.get(key), f'app.trade.strategy.spot_multi_signal_fusion.{key}')
        for key in (
            'technical_weight',
            'trade_flow_weight',
            'kline_breakout_weight',
            'kline_trend_breakout_weight',
            'min_confidence',
            'buy_threshold',
            'sell_threshold',
            'trade_flow_buy_ratio_threshold',
            'trade_flow_sell_ratio_threshold',
            'default_risk_per_trade',
        ):
            if float(fusion_cfg.get(key)) > 1:
                raise ConfigValidationError(f'配置项 app.trade.strategy.spot_multi_signal_fusion.{key} 不能大于 1')
        if float(fusion_cfg.get('trade_flow_imbalance_threshold')) > 1:
            raise ConfigValidationError('配置项 app.trade.strategy.spot_multi_signal_fusion.trade_flow_imbalance_threshold 不能大于 1')
        if float(fusion_cfg.get('trade_flow_sell_ratio_threshold')) >= float(fusion_cfg.get('trade_flow_buy_ratio_threshold')):
            raise ConfigValidationError('配置项 app.trade.strategy.spot_multi_signal_fusion.trade_flow_sell_ratio_threshold 必须小于 trade_flow_buy_ratio_threshold')
        enabled_node_count = sum(
            1
            for key in (
                'enable_technical_node',
                'enable_trade_flow_node',
                'enable_kline_breakout_node',
                'enable_kline_trend_breakout_node',
            )
            if bool(fusion_cfg.get(key))
        )
        if enabled_node_count <= 0:
            raise ConfigValidationError('配置项 app.trade.strategy.spot_multi_signal_fusion 至少要启用一种信号节点')
        if int(fusion_cfg.get('min_enabled_nodes')) > enabled_node_count:
            raise ConfigValidationError('配置项 app.trade.strategy.spot_multi_signal_fusion.min_enabled_nodes 不能大于已启用信号节点数')

        logging.info(
            '配置初始化完成: mode=%s provider=%s strategy_type=%s persistence_enabled=%s custom_gpt_base_url=%s',
            self.mode,
            self.gpt_provider,
            self.trade_strategy_type,
            self.trade_persistence_config.get('enabled'),
            bool(self.gpt_base_url),
        )
