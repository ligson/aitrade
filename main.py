# 运行机器人
import config.log_config
import config.config
from trade.trade import OptimizedCryptoBot

if __name__ == "__main__":
    config.log_config.config_log()
    cfg = config.config.Config("./config.yaml")
    bot = OptimizedCryptoBot(cfg)
    bot.run()
