import copy
import logging
import os

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


class ConfigValidationError(ValueError):
    """配置校验失败。"""



def load_config(config_file):
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
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

        self.trade_strategy_gpt_config = merge_config(
            DEFAULT_GPT_STRATEGY_CONFIG,
            strategy_cfg.get('gpt', {}),
        )
        self.trade_strategy_btc_spot_config = merge_config(
            DEFAULT_BTC_SPOT_BREAKOUT_CONFIG,
            strategy_cfg.get('btc_spot_breakout', {}),
        )

        _require_positive_number(
            self.trade_strategy_gpt_config.get('min_confidence'),
            'app.trade.strategy.gpt.min_confidence',
        )

        btc_spot_cfg = self.trade_strategy_btc_spot_config
        for key in (
            'donchian_entry',
            'donchian_exit',
            'ema_period',
            'ema_slope_lookback',
            'atr_period',
            'volume_ma_period',
        ):
            _require_positive_int(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')
        for key in (
            'atr_stop_mult',
            'atr_trail_mult',
            'breakout_buffer_bps',
            'volume_multiplier',
            'default_risk_per_trade',
        ):
            _require_positive_number(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')
        for key in ('confirm_macd', 'confirm_volume'):
            _require_bool(btc_spot_cfg.get(key), f'app.trade.strategy.btc_spot_breakout.{key}')
