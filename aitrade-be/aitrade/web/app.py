import traceback
from http import HTTPStatus

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.config_file import Config
from ..db import Base
from ..db.session import get_engine
from .api_response import success_response
from .exceptions import ApiError
from .modules.auth.router import router as auth_router
from .modules.backtests.router import router as backtests_router
from .modules.strategies.router import router as strategies_router
from .modules.system.router import router as system_router
from .modules.system.service import SystemService
from .modules.system.trade_task_service import TradeTaskService
from .modules.trade_logs.router import router as trade_logs_router
from .modules.users.router import router as users_router


def create_app(config: Config) -> FastAPI:
    engine = get_engine(config.trade_persistence_config['database_url'])
    Base.metadata.create_all(engine)

    app = FastAPI(title='aitrade-web', debug=config.web_debug)
    app.state.app_config = config
    app.state.system_service = SystemService(config)
    app.state.trade_task_service = TradeTaskService.from_config(config)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.web_cors_allow_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/health')
    async def health_get():
        return success_response({'status': 'ok'})

    @app.post('/health')
    async def health_post():
        return success_response({'status': 'ok'})

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError):
        trace = exc.trace or ''
        if trace and not config.web_show_trace:
            trace = ''
        payload = {
            'success': False,
            'message': exc.message,
            'trace': trace,
            'httpCode': exc.http_code,
            'data': {},
        }
        return JSONResponse(status_code=exc.http_code, content=payload)

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        payload = {
            'success': False,
            'message': detail,
            'trace': '',
            'httpCode': int(exc.status_code),
            'data': {},
        }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        trace = traceback.format_exc() if config.web_show_trace else ''
        payload = {
            'success': False,
            'message': str(exc),
            'trace': trace,
            'httpCode': int(HTTPStatus.INTERNAL_SERVER_ERROR),
            'data': {},
        }
        return JSONResponse(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, content=payload)

    app.include_router(auth_router, prefix='/api/auth', tags=['auth'])
    app.include_router(users_router, prefix='/api/users', tags=['users'])
    app.include_router(trade_logs_router, prefix='/api/trade-logs', tags=['trade-logs'])
    app.include_router(strategies_router, prefix='/api/strategies', tags=['strategies'])
    app.include_router(backtests_router, prefix='/api/backtests', tags=['backtests'])
    app.include_router(system_router, prefix='/api/system', tags=['system'])
    return app
