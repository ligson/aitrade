# 运行机器人
from .config import config_file
from .config import log_config
from .trade.trade import OptimizedCryptoBot

if __name__ == "__main__":
    log_config.config_log()
    cfg = config_file.Config("./config.yaml")
    bot = OptimizedCryptoBot(cfg)
    bot.run()
