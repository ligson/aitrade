import logging
import sys

import uvicorn

from .config import config_file
from .config import log_config
from .web import create_app


def main() -> int:
    try:
        log_config.config_log()
        cfg = config_file.Config('./config.yaml')
        app = create_app(cfg)
        uvicorn.run(app, host=cfg.web_host, port=cfg.web_port, log_level='info')
        return 0
    except config_file.ConfigValidationError as exc:
        logging.error('Web 配置校验失败: %s', exc)
        print(f'[ERROR] Web 配置校验失败: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        logging.exception('Web 服务启动失败: %s', exc)
        print(f'[ERROR] Web 服务启动失败: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
