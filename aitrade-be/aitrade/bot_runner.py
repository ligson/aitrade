import logging
import sys

from .config import config_file
from .config import log_config
from .trade.trade import OptimizedCryptoBot


def main() -> int:
    bot = None
    try:
        log_config.config_log()
        cfg = config_file.Config('./config.yaml', mode='bot')
        bot = OptimizedCryptoBot(cfg)
        bot.run()
        return 0
    except config_file.ConfigValidationError as exc:
        logging.error('配置校验失败: %s', exc)
        print(f'[ERROR] 配置校验失败: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        logging.exception('程序启动失败: %s', exc)
        print(f'[ERROR] 程序启动失败: {exc}', file=sys.stderr)
        return 1
    finally:
        if bot is not None:
            bot.close()


if __name__ == '__main__':
    raise SystemExit(main())
