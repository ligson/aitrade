from __future__ import annotations

import json
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from threading import Event
from threading import Lock
from threading import Thread
from typing import Any

from sqlalchemy import inspect
from sqlalchemy import text

from ....config.config_file import Config
from ....config.config_file import ConfigValidationError
from ....db import Base
from ....db import TradeTaskLogModel
from ....db import TradeTaskRuntimeModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.trade import OptimizedCryptoBot

STATUS_STOPPED = 'stopped'
STATUS_STARTING = 'starting'
STATUS_RUNNING = 'running'
STATUS_STOP_REQUESTED = 'stop_requested'
STATUS_FAILED = 'failed'
STATUS_CONFIG_ERROR = 'config_error'
STATUS_STALE = 'stale'
ACTIVE_STATUSES = {STATUS_STARTING, STATUS_RUNNING, STATUS_STOP_REQUESTED}
DEFAULT_RUNNER_NAME = 'default'
DEFAULT_LOG_LIMIT = 20


class TradeTaskService:
    _instances: dict[str, 'TradeTaskService'] = {}
    _instances_lock = Lock()

    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        self._lock = Lock()
        self._thread: Thread | None = None
        self._stop_event = Event()
        Base.metadata.create_all(self.engine)
        self._ensure_trade_task_runtime_schema()
        self._mark_stale_if_needed()

    @classmethod
    def from_config(cls, config: Config) -> 'TradeTaskService':
        database_url = config.trade_persistence_config['database_url']
        with cls._instances_lock:
            instance = cls._instances.get(database_url)
            if instance is None:
                instance = cls(config)
                cls._instances[database_url] = instance
            else:
                instance.config = config
            return instance

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            runtime = self._serialize_runtime(model)
            if runtime['status'] in ACTIVE_STATUSES and not self._is_thread_active():
                runtime = self._mark_stale_runtime(model)
            return self._serialize_runtime_with_logs(runtime)

    def list_logs(self, limit: int = DEFAULT_LOG_LIMIT) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or DEFAULT_LOG_LIMIT), 100))
        with self.Session() as session:
            models = (
                session.query(TradeTaskLogModel)
                .filter(TradeTaskLogModel.runner_name == DEFAULT_RUNNER_NAME)
                .order_by(TradeTaskLogModel.id.desc())
                .limit(normalized_limit)
                .all()
            )
            rows = [self._serialize_log(model) for model in models]
        return rows

    def _serialize_runtime_with_logs(self, runtime: dict[str, Any]) -> dict[str, Any]:
        payload = dict(runtime)
        payload['recentLogs'] = self.list_logs(limit=DEFAULT_LOG_LIMIT)
        return payload

    def start(self, current_user: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            if self._is_thread_active():
                return self._serialize_runtime_with_logs(self._serialize_runtime(model))
            if model.status in ACTIVE_STATUSES:
                self._mark_stale_runtime(model)
                model = self._get_or_create_runtime()

            now = self._now_iso()
            started_by = str(current_user.get('username') or current_user.get('nickname') or current_user.get('id') or '')
            model.status = STATUS_STARTING
            model.started_at = now
            model.stopped_at = None
            model.stop_requested_at = None
            model.last_heartbeat_at = now
            model.last_cycle_started_at = None
            model.last_cycle_finished_at = None
            model.next_run_at = None
            model.last_error = ''
            model.started_by = started_by
            model.symbol = None
            model.timeframe_minutes = None
            model.strategy_type = None
            model.updated_at = now
            self._save_runtime(model)
            self._append_log(
                event_type='start_requested',
                status=model.status,
                message='收到开始交易任务请求',
                detail={
                    'startedBy': started_by,
                },
            )

            self._stop_event = Event()
            self._thread = Thread(target=self._run_loop, args=(started_by,), daemon=True)
            self._thread.start()
            return self._serialize_runtime_with_logs(self._serialize_runtime(model))

    def stop(self) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            if model.status not in ACTIVE_STATUSES or not self._is_thread_active():
                if model.status in ACTIVE_STATUSES:
                    return self._serialize_runtime_with_logs(self._mark_stale_runtime(model))
                if model.status != STATUS_STOPPED:
                    now = self._now_iso()
                    model.status = STATUS_STOPPED
                    model.stopped_at = now
                    model.stop_requested_at = now
                    model.next_run_at = None
                    model.updated_at = now
                    self._save_runtime(model)
                return self._serialize_runtime_with_logs(self._serialize_runtime(model))

            now = self._now_iso()
            model.status = STATUS_STOP_REQUESTED
            model.stop_requested_at = now
            model.next_run_at = None
            model.updated_at = now
            self._save_runtime(model)
            self._append_log(
                event_type='stop_requested',
                status=model.status,
                message='收到停止交易任务请求',
                detail={
                    'stopRequestedAt': now,
                },
            )
            self._stop_event.set()
            return self._serialize_runtime_with_logs(self._serialize_runtime(model))

    def _run_loop(self, started_by: str) -> None:
        bot = None
        try:
            runtime_config = Config('./config.yaml')
            bot = OptimizedCryptoBot(runtime_config)
            now = self._now_iso()
            with self._lock:
                model = self._get_or_create_runtime()
                model.status = STATUS_RUNNING
                model.started_at = model.started_at or now
                model.stopped_at = None
                model.stop_requested_at = None
                model.last_heartbeat_at = now
                model.last_cycle_started_at = None
                model.last_cycle_finished_at = None
                model.next_run_at = self._add_seconds(now, runtime_config.trade_timeframe * 60)
                model.last_error = ''
                model.started_by = started_by
                model.symbol = runtime_config.trade_symbol
                model.timeframe_minutes = runtime_config.trade_timeframe
                model.strategy_type = runtime_config.trade_strategy_type
                model.updated_at = now
                self._save_runtime(model)
                self._append_log(
                    event_type='started',
                    status=model.status,
                    message='交易任务已启动',
                    detail={
                        'startedBy': started_by,
                        'symbol': runtime_config.trade_symbol,
                        'timeframeMinutes': runtime_config.trade_timeframe,
                        'strategyType': runtime_config.trade_strategy_type,
                    },
                )

            while not self._stop_event.is_set():
                cycle_started_at = self._now_iso()
                with self._lock:
                    model = self._get_or_create_runtime()
                    model.status = STATUS_RUNNING
                    model.last_heartbeat_at = cycle_started_at
                    model.last_cycle_started_at = cycle_started_at
                    model.next_run_at = None
                    model.updated_at = cycle_started_at
                    self._save_runtime(model)
                    self._append_log(
                        event_type='cycle_started',
                        status=model.status,
                        message='开始新的交易周期',
                        detail={
                            'cycleStartedAt': cycle_started_at,
                            'symbol': model.symbol,
                            'strategyType': model.strategy_type,
                        },
                    )

                bot.trading_bot.run_cycle()

                cycle_finished_at = self._now_iso()
                interval_seconds = bot.trading_bot.get_cycle_interval_seconds()
                with self._lock:
                    model = self._get_or_create_runtime()
                    if model.status != STATUS_STOP_REQUESTED:
                        model.status = STATUS_RUNNING
                    model.last_heartbeat_at = cycle_finished_at
                    model.last_cycle_finished_at = cycle_finished_at
                    model.next_run_at = self._add_seconds(cycle_finished_at, interval_seconds)
                    model.updated_at = cycle_finished_at
                    self._save_runtime(model)
                    self._append_log(
                        event_type='cycle_finished',
                        status=model.status,
                        message='交易周期执行完成',
                        detail={
                            'cycleFinishedAt': cycle_finished_at,
                            'nextRunAt': model.next_run_at,
                        },
                    )

                if self._stop_event.wait(interval_seconds):
                    break

            stopped_at = self._now_iso()
            with self._lock:
                model = self._get_or_create_runtime()
                model.status = STATUS_STOPPED
                model.stopped_at = stopped_at
                model.next_run_at = None
                model.last_heartbeat_at = stopped_at
                model.updated_at = stopped_at
                self._save_runtime(model)
                self._append_log(
                    event_type='stopped',
                    status=model.status,
                    message='交易任务已停止',
                    detail={
                        'stoppedAt': stopped_at,
                    },
                )
        except ConfigValidationError as exc:
            self._mark_failed(STATUS_CONFIG_ERROR, str(exc))
        except Exception as exc:
            logging.exception('交易任务运行失败: %s', exc)
            self._mark_failed(STATUS_FAILED, str(exc))
        finally:
            if bot is not None:
                bot.close()
            with self._lock:
                self._thread = None
                self._stop_event = Event()

    def _mark_failed(self, status: str, error_message: str) -> None:
        now = self._now_iso()
        with self._lock:
            model = self._get_or_create_runtime()
            model.status = status
            model.stopped_at = now
            model.next_run_at = None
            model.last_heartbeat_at = now
            model.last_error = error_message
            model.updated_at = now
            self._save_runtime(model)
            self._append_log(
                event_type='failed',
                status=model.status,
                message='交易任务运行失败',
                detail={
                    'errorMessage': error_message,
                    'stoppedAt': now,
                },
            )

    def _mark_stale_if_needed(self) -> None:
        with self._lock:
            model = self._get_or_create_runtime()
            if model.status in ACTIVE_STATUSES and not self._is_thread_active():
                self._mark_stale_runtime(model)

    def _mark_stale_runtime(self, model: TradeTaskRuntimeModel) -> dict[str, Any]:
        now = self._now_iso()
        model.status = STATUS_STALE
        model.stopped_at = now
        model.next_run_at = None
        model.last_error = model.last_error or '检测到交易任务状态残留，当前 Web 进程内没有活动任务线程'
        model.updated_at = now
        self._save_runtime(model)
        self._append_log(
            event_type='stale',
            status=model.status,
            message='检测到交易任务状态残留',
            detail={
                'stoppedAt': now,
                'errorMessage': model.last_error,
            },
        )
        return self._serialize_runtime(model)

    def _is_thread_active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _get_or_create_runtime(self) -> TradeTaskRuntimeModel:
        with self.Session() as session:
            model = session.get(TradeTaskRuntimeModel, DEFAULT_RUNNER_NAME)
            if model is None:
                now = self._now_iso()
                model = TradeTaskRuntimeModel(
                    runner_name=DEFAULT_RUNNER_NAME,
                    status=STATUS_STOPPED,
                    started_at=None,
                    stopped_at=None,
                    stop_requested_at=None,
                    last_heartbeat_at=None,
                    last_cycle_started_at=None,
                    last_cycle_finished_at=None,
                    next_run_at=None,
                    last_error='',
                    started_by=None,
                    symbol=None,
                    timeframe_minutes=None,
                    strategy_type=None,
                    updated_at=now,
                )
                session.add(model)
                session.commit()
                session.refresh(model)
            return self._clone_model(model)

    def _save_runtime(self, runtime: TradeTaskRuntimeModel) -> None:
        with self.Session() as session:
            model = session.get(TradeTaskRuntimeModel, runtime.runner_name)
            if model is None:
                model = TradeTaskRuntimeModel(runner_name=runtime.runner_name, status=runtime.status, updated_at=runtime.updated_at)
                session.add(model)
            model.status = runtime.status
            model.started_at = runtime.started_at
            model.stopped_at = runtime.stopped_at
            model.stop_requested_at = runtime.stop_requested_at
            model.last_heartbeat_at = runtime.last_heartbeat_at
            model.last_cycle_started_at = runtime.last_cycle_started_at
            model.last_cycle_finished_at = runtime.last_cycle_finished_at
            model.next_run_at = runtime.next_run_at
            model.last_error = runtime.last_error
            model.started_by = runtime.started_by
            model.symbol = runtime.symbol
            model.timeframe_minutes = runtime.timeframe_minutes
            model.strategy_type = runtime.strategy_type
            model.updated_at = runtime.updated_at
            session.commit()

    @staticmethod
    def _clone_model(model: TradeTaskRuntimeModel) -> TradeTaskRuntimeModel:
        return TradeTaskRuntimeModel(
            runner_name=model.runner_name,
            status=model.status,
            started_at=model.started_at,
            stopped_at=model.stopped_at,
            stop_requested_at=model.stop_requested_at,
            last_heartbeat_at=model.last_heartbeat_at,
            last_cycle_started_at=model.last_cycle_started_at,
            last_cycle_finished_at=model.last_cycle_finished_at,
            next_run_at=model.next_run_at,
            last_error=model.last_error,
            started_by=model.started_by,
            symbol=model.symbol,
            timeframe_minutes=model.timeframe_minutes,
            strategy_type=model.strategy_type,
            updated_at=model.updated_at,
        )

    def _serialize_runtime(self, model: TradeTaskRuntimeModel) -> dict[str, Any]:
        is_running = model.status in ACTIVE_STATUSES and self._is_thread_active()
        return {
            'runnerName': model.runner_name,
            'status': model.status,
            'isRunning': is_running,
            'canStart': model.status not in ACTIVE_STATUSES or not self._is_thread_active(),
            'canStop': model.status in ACTIVE_STATUSES and self._is_thread_active(),
            'startedAt': model.started_at,
            'stoppedAt': model.stopped_at,
            'stopRequestedAt': model.stop_requested_at,
            'lastHeartbeatAt': model.last_heartbeat_at,
            'lastCycleStartedAt': model.last_cycle_started_at,
            'lastCycleFinishedAt': model.last_cycle_finished_at,
            'nextRunAt': model.next_run_at,
            'lastError': model.last_error or '',
            'startedBy': model.started_by or '',
            'symbol': model.symbol or '',
            'timeframeMinutes': model.timeframe_minutes,
            'strategyType': model.strategy_type or '',
            'updatedAt': model.updated_at,
        }

    def _append_log(self, event_type: str, status: str, message: str, detail: dict[str, Any] | None = None) -> None:
        now = self._now_iso()
        with self.Session() as session:
            session.add(
                TradeTaskLogModel(
                    runner_name=DEFAULT_RUNNER_NAME,
                    event_type=event_type,
                    status=status,
                    message=message,
                    detail_json=json.dumps(detail or {}, ensure_ascii=False),
                    created_at=now,
                )
            )
            session.commit()

    @staticmethod
    def _serialize_log(model: TradeTaskLogModel) -> dict[str, Any]:
        return {
            'id': model.id,
            'runnerName': model.runner_name,
            'eventType': model.event_type,
            'status': model.status,
            'message': model.message,
            'detail': json.loads(model.detail_json or '{}'),
            'createdAt': model.created_at,
        }

    def _ensure_trade_task_runtime_schema(self) -> None:
        inspector = inspect(self.engine)
        if 'trade_task_runtime' in inspector.get_table_names():
            columns = {column['name'] for column in inspector.get_columns('trade_task_runtime')}
            column_definitions = {
                'started_at': 'VARCHAR',
                'stopped_at': 'VARCHAR',
                'stop_requested_at': 'VARCHAR',
                'last_heartbeat_at': 'VARCHAR',
                'last_cycle_started_at': 'VARCHAR',
                'last_cycle_finished_at': 'VARCHAR',
                'next_run_at': 'VARCHAR',
                'last_error': 'TEXT',
                'started_by': 'VARCHAR',
                'symbol': 'VARCHAR',
                'timeframe_minutes': 'INTEGER',
                'strategy_type': 'VARCHAR',
                'updated_at': 'VARCHAR',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            if missing_columns:
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_runtime ADD COLUMN {name} {ddl}'))

        if 'trade_task_logs' in inspector.get_table_names():
            columns = {column['name'] for column in inspector.get_columns('trade_task_logs')}
            column_definitions = {
                'detail_json': 'TEXT',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            if missing_columns:
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_logs ADD COLUMN {name} {ddl}'))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _add_seconds(value: str, seconds: int) -> str:
        return (datetime.fromisoformat(value) + timedelta(seconds=seconds)).isoformat()
