# 运行机器人
import config.log_config
from trade.trade import OptimizedCryptoBot

if __name__ == "__main__":
    config.log_config.config_log()
    bot = OptimizedCryptoBot()
    bot.run()
