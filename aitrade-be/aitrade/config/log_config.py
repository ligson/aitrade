import datetime
import logging
import os
from logging.handlers import TimedRotatingFileHandler

import colorlog
import yaml

from .path_utils import normalize_filesystem_path
from .path_utils import resolve_default_data_root_dir
from .path_utils import resolve_default_log_dir
from .path_utils import resolve_log_dir as resolve_log_dir_from_data_root


def resolve_log_dir(config_file: str = './config.yaml') -> str:
    default_log_dir = resolve_default_log_dir()
    try:
        if not os.path.exists(config_file):
            return default_log_dir
        with open(config_file, 'r', encoding='utf-8') as file:
            config_data = yaml.safe_load(file) or {}
        app_cfg = config_data.get('app') or {}
        data_root_dir = app_cfg.get('data_root_dir')
        if isinstance(data_root_dir, str) and data_root_dir.strip():
            return resolve_log_dir_from_data_root(data_root_dir)
        log_dir = app_cfg.get('log_dir')
        if not isinstance(log_dir, str) or not log_dir.strip():
            return default_log_dir
        return normalize_filesystem_path(log_dir)
    except Exception as exc:
        fallback_root = resolve_default_data_root_dir()
        print(f'[WARN] 读取日志目录配置失败，回退到默认目录 {default_log_dir}（data_root_dir 默认 {fallback_root}）: {exc}')
        return default_log_dir


def config_log(config_file: str = './config.yaml'):
    log_dir = resolve_log_dir(config_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 设置日志文件名，包含日期和时间
    log_file = datetime.datetime.now().strftime("%Y-%m-%d-%H.log")
    logout = os.path.join(log_dir, log_file)
    print("日志文件路径: " + logout)

    # 配置文件日志处理器
    file_handler = TimedRotatingFileHandler(logout, when="H", interval=1, backupCount=72)  # 每小时生成一个文件，保留72个文件（3天）
    file_handler.setFormatter(logging.Formatter('%(asctime)s-[%(levelname)s]-%(filename)s: %(message)s'))
    file_handler.setLevel(logging.DEBUG)

    # 配置控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # 创建 ColorFormatter 实例，设置不同级别日志的颜色
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s%(reset)s-[%(log_color)s%(levelname)s%(reset)s]-%(yellow)s%(filename)s%(reset)s ==> %(white)s%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        },
        reset=True
    )

    console_handler.setFormatter(formatter)

    # 创建专门用于交易日志的处理器
    trade_log_file = datetime.datetime.now().strftime("trade_%Y-%m-%d-%H.log")
    trade_logout = os.path.join(log_dir, trade_log_file)
    trade_file_handler = TimedRotatingFileHandler(trade_logout, when="H", interval=1, backupCount=72)
    trade_file_handler.setFormatter(logging.Formatter('%(asctime)s-[%(levelname)s]-%(filename)s: %(message)s'))
    trade_file_handler.setLevel(logging.INFO)
    
    # 创建交易日志记录器并添加处理器
    trade_logger = logging.getLogger('trade')
    trade_logger.addHandler(trade_file_handler)
    trade_logger.setLevel(logging.INFO)
    # 防止传播到根日志记录器，避免重复记录
    trade_logger.propagate = False

    # 创建日志记录器并添加处理器
    logger = logging.getLogger('')
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)