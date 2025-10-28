import datetime
import logging
import os
from logging.handlers import TimedRotatingFileHandler

import colorlog


def config_log():
    log_dir = os.path.join(os.getcwd(), "logs")
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
        '%(log_color)s%(asctime)s%(reset)s-[%(log_color)s%(levelname)s%(reset)s]-%(yellow)s%(filename)s%(reset)s: %(white)s%(message)s',
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

    # 创建日志记录器并添加处理器
    logger = logging.getLogger('')
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG)
