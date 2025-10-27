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
        self.db_host = app_cfg['db']['host']
        self.db_port = app_cfg['db']['port']
        self.db_user = app_cfg['db']['user']
        self.db_password = app_cfg['db']['password']
        self.db_name = app_cfg['db']['db_name']
        self.pool_size = app_cfg['db'].get('pool_size', 5)  # 默认值为 5
        self.max_connections = app_cfg['db'].get('max_connections', 10)  # 默认值为 10
        self.idle_connections = app_cfg['db'].get('idle_connections', 2)  # 默认值为 2
        self.connect_timeout = app_cfg['db'].get('connect_timeout', 10)  # 默认值为 10
        self.proxy_url = app_cfg["proxy"]["url"]
        self.rss_url = app_cfg["rss"]["url"]
        self.tg_token = app_cfg["tg"]["bot_token"]
        self.tg_chat_ids = app_cfg["tg"]["chat_ids"]
