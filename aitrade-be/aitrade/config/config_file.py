import copy
import logging
import os
from typing import Any
from typing import Dict

import yaml


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

DEFAULT_TRADE_PERSISTENCE_CONFIG = {
    'enabled': True,
    'database_url': 'sqlite:///./.aitrade/trades.sqlite3',
    'persist_position': True,
    'restore_position_on_startup': False,
}

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
    'data_dir': './.aitrade/backtest-data',
    'user_data_dir': './.aitrade/freqtrade-user-data',
    'supported_symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
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


def _require_string_list(value, path):
    if not isinstance(value, list):
        raise ConfigValidationError(f"配置项 {path} 必须是字符串数组")
    items = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigValidationError(f"配置项 {path}[{index}] 必须是非空字符串")
        items.append(item.strip())
    return items


class Config:
    def __init__(self, config_file):
        if os.path.exists(config_file):
            logging.info("配置文件存在，绝对路径：%s", os.path.abspath(config_file))
        else:
            logging.info("%s配置文件不存在", config_file)

        self.config = load_config(config_file)
        if not isinstance(self.config, dict):
            raise ConfigValidationError("config.yaml 顶层结构必须是对象，且至少包含 app 配置")

        app_cfg = _require_mapping(self.config.get('app'), 'app')

        gpt_cfg = _require_mapping(app_cfg.get('gpt'), 'app.gpt')
        self.gpt_provider = _require_non_empty_string(gpt_cfg.get('provider'), 'app.gpt.provider')
        if self.gpt_provider not in {'deepseek', 'openai'}:
            raise ConfigValidationError("配置项 app.gpt.provider 只支持 deepseek 或 openai")
        self.gpt_api_key = _require_non_empty_string(gpt_cfg.get('api_key'), 'app.gpt.api_key')
        self.gpt_model = _require_non_empty_string(gpt_cfg.get('model', 'deepseek-chat'), 'app.gpt.model')

        http_client_cfg = _require_mapping(app_cfg.get('http_client'), 'app.http_client')
        self.proxy_enable = _require_bool(http_client_cfg.get('proxy_enable', False), 'app.http_client.proxy_enable')
        self.proxy_url = http_client_cfg.get('proxy_url')
        if self.proxy_enable:
            self.proxy_url = _require_non_empty_string(self.proxy_url, 'app.http_client.proxy_url')
        elif self.proxy_url is not None and not isinstance(self.proxy_url, str):
            raise ConfigValidationError("配置项 app.http_client.proxy_url 必须是字符串")

        exchange_cfg = _require_mapping(app_cfg.get('exchange'), 'app.exchange')
        self.exchange_type = _require_non_empty_string(exchange_cfg.get('type'), 'app.exchange.type')
        if self.exchange_type not in {'binance', 'okx'}:
            raise ConfigValidationError("配置项 app.exchange.type 只支持 binance 或 okx")
        self.exchange_api_key = _require_non_empty_string(exchange_cfg.get('api_key'), 'app.exchange.api_key')
        self.exchange_api_secret = _require_non_empty_string(exchange_cfg.get('api_secret'), 'app.exchange.api_secret')
        password = exchange_cfg.get('password', '')
        if password is None:
            password = ''
        if not isinstance(password, str):
            raise ConfigValidationError("配置项 app.exchange.password 必须是字符串")
        self.exchange_password = password
        if self.exchange_type == 'okx' and not self.exchange_password.strip():
            raise ConfigValidationError("使用 OKX 时，配置项 app.exchange.password 不能为空")

        trade_cfg = _require_mapping(app_cfg.get('trade'), 'app.trade')
        self.trade_sandbox_trade = _require_bool(trade_cfg.get('sandbox_trade', True), 'app.trade.sandbox_trade')
        self.trade_symbol = _require_non_empty_string(trade_cfg.get('symbol', 'BTC/USDT'), 'app.trade.symbol')
        self.trade_timeframe = _require_positive_int(trade_cfg.get('timeframe', 15), 'app.trade.timeframe')
        self.trade_limit = _require_positive_int(trade_cfg.get('limit', 100), 'app.trade.limit')

        strategy_cfg = _require_mapping(trade_cfg.get('strategy'), 'app.trade.strategy')
        self.trade_strategy_type = _require_non_empty_string(strategy_cfg.get('type', 'gpt'), 'app.trade.strategy.type')
        if self.trade_strategy_type not in {'gpt', 'btc_spot_breakout'}:
            raise ConfigValidationError("配置项 app.trade.strategy.type 只支持 gpt 或 btc_spot_breakout")

        self.trade_strategy_gpt_config = merge_config(DEFAULT_GPT_STRATEGY_CONFIG, strategy_cfg.get('gpt', {}))
        self.trade_strategy_btc_spot_config = merge_config(DEFAULT_BTC_SPOT_BREAKOUT_CONFIG, strategy_cfg.get('btc_spot_breakout', {}))

        persistence_overrides = trade_cfg.get('persistence', {})
        if persistence_overrides is None:
            persistence_overrides = {}
        persistence_overrides = _require_mapping(persistence_overrides, 'app.trade.persistence')
        self.trade_persistence_config = merge_config(DEFAULT_TRADE_PERSISTENCE_CONFIG, persistence_overrides)

        _require_bool(self.trade_persistence_config.get('enabled'), 'app.trade.persistence.enabled')
        database_url = persistence_overrides.get('database_url')
        # sqlite_path 仅用于兼容旧配置，新的配置文件统一使用 database_url。
        if database_url is None and persistence_overrides.get('sqlite_path') is not None:
            sqlite_path = _require_non_empty_string(
                persistence_overrides.get('sqlite_path'),
                'app.trade.persistence.sqlite_path',
            )
            database_url = f'sqlite:///{sqlite_path}'
        self.trade_persistence_config['database_url'] = _require_non_empty_string(
            database_url or self.trade_persistence_config.get('database_url'),
            'app.trade.persistence.database_url',
        )
        if persistence_overrides.get('sqlite_path') is not None:
            self.trade_persistence_config['sqlite_path'] = _require_non_empty_string(
                persistence_overrides.get('sqlite_path'),
                'app.trade.persistence.sqlite_path',
            )
        _require_bool(self.trade_persistence_config.get('persist_position'), 'app.trade.persistence.persist_position')
        _require_bool(
            self.trade_persistence_config.get('restore_position_on_startup'),
            'app.trade.persistence.restore_position_on_startup',
        )

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

        backtest_overrides = app_cfg.get('backtest', {})
        if backtest_overrides is None:
            backtest_overrides = {}
        backtest_overrides = _require_mapping(backtest_overrides, 'app.backtest')
        self.backtest_config = merge_config(DEFAULT_BACKTEST_CONFIG, backtest_overrides)
        self.backtest_config['data_dir'] = _require_non_empty_string(self.backtest_config.get('data_dir'), 'app.backtest.data_dir')
        self.backtest_config['user_data_dir'] = _require_non_empty_string(
            self.backtest_config.get('user_data_dir'),
            'app.backtest.user_data_dir',
        )
        self.backtest_config['supported_symbols'] = _require_string_list(
            self.backtest_config.get('supported_symbols'),
            'app.backtest.supported_symbols',
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
