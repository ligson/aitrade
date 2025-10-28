import logging
import os

import yaml


def load_config(config_file):
    with open(config_file, 'r') as file:
        config = yaml.safe_load(file)
    return config


class Config:
    def __init__(self, config_file):

        if os.path.exists(config_file):
            logging.info("配置文件存在，绝对路径：%s", os.path.abspath(config_file))
        else:
            logging.info("%s配置文件不存在", config_file)

        self.config = load_config(config_file)

        # 从配置文件中获取数据库配置
        app_cfg = self.config['app']
        # --- GPT 配置 (使用 app['gpt'] 格式取值) ---
        gpt_cfg = app_cfg.get('gpt', {})
        self.gpt_provider = gpt_cfg.get('provider')
        self.gpt_api_key = gpt_cfg.get('api_key')

        # --- 代理配置 (使用 app['http_client']['proxy_url'] 格式取值) ---
        http_client_cfg = app_cfg.get('http_client', {})
        # 正确的取值路径是 app['http_client']['proxy_url']
        self.proxy_url = http_client_cfg.get('proxy_url')

        # 补充获取代理启用状态
        self.proxy_enable = http_client_cfg.get('proxy_enable', False)

        # --- Exchange (交易接口) 配置 ---
        exchange_cfg = app_cfg.get('exchange', {})
        self.exchange_type = exchange_cfg.get('type')
        self.exchange_api_key = exchange_cfg.get('api_key')
        self.exchange_api_secret = exchange_cfg.get('api_secret')

        # --- Trade (交易) 配置 ---
        trade_cfg = app_cfg.get('trade', {})
        self.trade_sandbox_trade = trade_cfg.get('sandbox_trade', True)
        # 交易对,默认BTC/USDT
        self.trade_symbol = trade_cfg.get('symbol', 'BTC/USDT')
        # 交易时间间隔,默认15m
        self.trade_timeframe = trade_cfg.get('timeframe', 15)
        # 交易数据个数,默认100
        self.trade_limit = trade_cfg.get('limit', 100)
