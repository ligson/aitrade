from __future__ import annotations

import copy
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
from sqlalchemy import or_
from sqlalchemy import text

from ....config.config_file import Config
from ....config.config_file import ConfigValidationError
from ....db import Base
from ....db import StrategyProfileModel
from ....db import TradeTaskLogModel
from ....db import TradeTaskProfileModel
from ....db import TradeTaskRunModel
from ....db import TradeTaskRuntimeModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.strategies.registry import get_strategy_definition
from ....trade.trade import OptimizedCryptoBot
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ..strategies.params import normalize_strategy_params

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

    def list_profiles(self) -> list[dict[str, Any]]:
        with self.Session() as session:
            strategy_profiles = {
                item.id: item
                for item in session.query(StrategyProfileModel).order_by(StrategyProfileModel.id.asc()).all()
            }
            models = session.query(TradeTaskProfileModel).order_by(TradeTaskProfileModel.id.asc()).all()
            return [self._serialize_profile(model, strategy_profiles.get(model.strategy_profile_id)) for model in models]

    def save_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get('name') or '').strip()
        if not name:
            raise ValidationError('交易任务配置名称不能为空')
        strategy_profile_id = int(payload.get('strategyProfileId') or 0)
        if strategy_profile_id <= 0:
            raise ValidationError('请选择策略配置')
        symbol = str(payload.get('symbol') or '').strip()
        if not symbol:
            raise ValidationError('交易对不能为空')
        timeframe = self._normalize_timeframe(str(payload.get('timeframe') or '').strip())
        trade_limit = int(payload.get('tradeLimit') or 0)
        if trade_limit <= 0:
            raise ValidationError('K 线数量必须大于 0')
        runner_name = str(payload.get('runnerName') or DEFAULT_RUNNER_NAME).strip() or DEFAULT_RUNNER_NAME
        if runner_name != DEFAULT_RUNNER_NAME:
            raise ValidationError('当前仅支持 default runner')
        enabled = bool(payload.get('enabled', True))
        description = str(payload.get('description') or '').strip()
        sandbox_trade = bool(payload.get('sandboxTrade', True))
        profile_id = payload.get('id')
        now = self._now_iso()

        with self.Session() as session:
            strategy_profile = session.get(StrategyProfileModel, strategy_profile_id)
            if strategy_profile is None:
                raise NotFoundError('策略配置不存在')
            if not strategy_profile.enabled:
                raise ValidationError('所选策略配置已停用')

            if profile_id is None:
                model = TradeTaskProfileModel(
                    name=name,
                    description=description,
                    enabled=enabled,
                    strategy_profile_id=strategy_profile.id,
                    strategy_type=strategy_profile.strategy_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    sandbox_trade=sandbox_trade,
                    trade_limit=trade_limit,
                    runner_name=runner_name,
                    created_at=now,
                    updated_at=now,
                )
                session.add(model)
                session.commit()
                session.refresh(model)
            else:
                model = session.get(TradeTaskProfileModel, int(profile_id))
                if model is None:
                    raise NotFoundError('交易任务配置不存在')
                model.name = name
                model.description = description
                model.enabled = enabled
                model.strategy_profile_id = strategy_profile.id
                model.strategy_type = strategy_profile.strategy_type
                model.symbol = symbol
                model.timeframe = timeframe
                model.sandbox_trade = sandbox_trade
                model.trade_limit = trade_limit
                model.runner_name = runner_name
                model.updated_at = now
                session.commit()
                session.refresh(model)
            return self._serialize_profile(model, strategy_profile)

    def delete_profile(self, profile_id: int) -> dict[str, Any]:
        with self.Session() as session:
            model = session.get(TradeTaskProfileModel, profile_id)
            if model is None:
                raise NotFoundError('交易任务配置不存在')
            runtime = session.get(TradeTaskRuntimeModel, model.runner_name)
            if runtime is not None and runtime.trade_task_profile_id == model.id and runtime.status in ACTIVE_STATUSES:
                raise ValidationError('当前交易任务正在使用该配置，不能删除')
            session.delete(model)
            session.commit()
        return {'deleted': True, 'id': profile_id}

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            runtime = self._serialize_runtime(model)
            if runtime['status'] in ACTIVE_STATUSES and not self._is_thread_active():
                runtime = self._mark_stale_runtime(model)
        payload = dict(runtime)
        payload['recentLogs'] = self.list_logs(limit=DEFAULT_LOG_LIMIT, run_id=payload.get('runId'))
        payload['currentRun'] = self.get_run_detail(payload['runId']) if payload.get('runId') else None
        return payload

    def get_run_detail(self, run_id: int) -> dict[str, Any] | None:
        with self.Session() as session:
            model = session.get(TradeTaskRunModel, run_id)
            return self._serialize_run(model) if model is not None else None

    def list_logs(self, limit: int = DEFAULT_LOG_LIMIT, run_id: int | None = None) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or DEFAULT_LOG_LIMIT), 100))
        with self.Session() as session:
            query = session.query(TradeTaskLogModel)
            if run_id is not None:
                query = query.filter(TradeTaskLogModel.run_id == run_id)
            else:
                query = query.filter(TradeTaskLogModel.runner_name == DEFAULT_RUNNER_NAME)
            models = query.order_by(TradeTaskLogModel.id.desc()).limit(normalized_limit).all()
            return self._serialize_logs(session, models)

    def page_logs(
        self,
        offset: int = 0,
        size: int = 20,
        runner_name: str | None = None,
        run_id: int | None = None,
        event_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        normalized_offset = max(0, int(offset or 0))
        normalized_size = max(1, min(int(size or 20), 100))
        normalized_runner_name = (runner_name or DEFAULT_RUNNER_NAME).strip()
        normalized_run_id = int(run_id) if run_id else None
        normalized_event_type = (event_type or '').strip()
        normalized_status = (status or '').strip()
        normalized_keyword = (keyword or '').strip()
        normalized_created_from = (created_from or '').strip()
        normalized_created_to = (created_to or '').strip()

        with self.Session() as session:
            query = session.query(TradeTaskLogModel).filter(TradeTaskLogModel.runner_name == normalized_runner_name)
            if normalized_run_id is not None:
                query = query.filter(TradeTaskLogModel.run_id == normalized_run_id)
            if normalized_event_type:
                query = query.filter(TradeTaskLogModel.event_type == normalized_event_type)
            if normalized_status:
                query = query.filter(TradeTaskLogModel.status == normalized_status)
            if normalized_created_from:
                query = query.filter(TradeTaskLogModel.created_at >= normalized_created_from)
            if normalized_created_to:
                query = query.filter(TradeTaskLogModel.created_at <= normalized_created_to)
            if normalized_keyword:
                like_keyword = f'%{normalized_keyword}%'
                query = query.filter(
                    or_(
                        TradeTaskLogModel.message.like(like_keyword),
                        TradeTaskLogModel.detail_json.like(like_keyword),
                    )
                )
            total = query.count()
            models = query.order_by(TradeTaskLogModel.id.desc()).offset(normalized_offset).limit(normalized_size).all()
            return total, self._serialize_logs(session, models)

    def start(self, trade_task_profile_id: int, current_user: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            if self._is_thread_active():
                return self._wrap_status_payload(self._serialize_runtime(model))
            if model.status in ACTIVE_STATUSES:
                self._mark_stale_runtime(model)
                model = self._get_or_create_runtime()

            run = self._create_run_snapshot(trade_task_profile_id, current_user)
            now = self._now_iso()
            started_by = run['createdBy']
            model.run_id = run['id']
            model.trade_task_profile_id = run['tradeTaskProfileId']
            model.profile_name = run['profileName']
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
            model.symbol = run['symbol']
            model.timeframe = run['timeframe']
            model.timeframe_minutes = self._timeframe_to_minutes(run['timeframe'])
            model.strategy_type = run['strategyType']
            model.updated_at = now
            self._save_runtime(model)
            self._append_log(
                run_id=run['id'],
                event_type='start_requested',
                status=model.status,
                message='收到开始交易任务请求',
                detail={
                    'startedBy': started_by,
                    'profileName': run['profileName'],
                    'symbol': run['symbol'],
                    'timeframe': run['timeframe'],
                    'strategyType': run['strategyType'],
                },
            )
            self._stop_event = Event()
            self._thread = Thread(target=self._run_loop, args=(run['id'], started_by), daemon=True)
            self._thread.start()
            return self._wrap_status_payload(self._serialize_runtime(model))

    def stop(self) -> dict[str, Any]:
        with self._lock:
            model = self._get_or_create_runtime()
            if model.status not in ACTIVE_STATUSES or not self._is_thread_active():
                if model.status in ACTIVE_STATUSES:
                    return self._wrap_status_payload(self._mark_stale_runtime(model))
                if model.status != STATUS_STOPPED:
                    now = self._now_iso()
                    model.status = STATUS_STOPPED
                    model.stopped_at = now
                    model.stop_requested_at = now
                    model.next_run_at = None
                    model.updated_at = now
                    self._save_runtime(model)
                return self._wrap_status_payload(self._serialize_runtime(model))

            now = self._now_iso()
            model.status = STATUS_STOP_REQUESTED
            model.stop_requested_at = now
            model.next_run_at = None
            model.updated_at = now
            self._save_runtime(model)
            if model.run_id:
                self._update_run_status(model.run_id, status=STATUS_STOP_REQUESTED, stop_requested_at=now)
            self._append_log(
                run_id=model.run_id,
                event_type='stop_requested',
                status=model.status,
                message='收到停止交易任务请求',
                detail={
                    'stopRequestedAt': now,
                },
            )
            self._stop_event.set()
            return self._wrap_status_payload(self._serialize_runtime(model))

    def _create_run_snapshot(self, trade_task_profile_id: int, current_user: dict[str, Any]) -> dict[str, Any]:
        with self.Session() as session:
            profile = session.get(TradeTaskProfileModel, trade_task_profile_id)
            if profile is None:
                raise NotFoundError('交易任务配置不存在')
            if not profile.enabled:
                raise ValidationError('交易任务配置已停用，不能启动')
            strategy_profile = session.get(StrategyProfileModel, profile.strategy_profile_id)
            if strategy_profile is None:
                raise NotFoundError('关联策略配置不存在')
            if not strategy_profile.enabled:
                raise ValidationError('关联策略配置已停用，不能启动')
            definition = get_strategy_definition(strategy_profile.strategy_type)
            normalized_params = normalize_strategy_params(definition, json.loads(strategy_profile.params_json or '{}'))
            now = self._now_iso()
            created_by = str(current_user.get('username') or current_user.get('nickname') or current_user.get('id') or '')
            snapshot = {
                'profileId': profile.id,
                'profileName': profile.name,
                'runnerName': profile.runner_name,
                'strategyProfileId': strategy_profile.id,
                'strategyProfileName': strategy_profile.name,
                'strategyType': strategy_profile.strategy_type,
                'strategySchemaVersion': definition['schemaVersion'],
                'strategyParams': normalized_params,
                'symbol': profile.symbol,
                'timeframe': profile.timeframe,
                'sandboxTrade': bool(profile.sandbox_trade),
                'tradeLimit': int(profile.trade_limit),
            }
            run = TradeTaskRunModel(
                runner_name=profile.runner_name,
                trade_task_profile_id=profile.id,
                profile_name=profile.name,
                strategy_profile_id=strategy_profile.id,
                strategy_type=strategy_profile.strategy_type,
                strategy_schema_version=definition['schemaVersion'],
                symbol=profile.symbol,
                timeframe=profile.timeframe,
                sandbox_trade=bool(profile.sandbox_trade),
                trade_limit=int(profile.trade_limit),
                strategy_params_json=json.dumps(normalized_params, ensure_ascii=False),
                snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                status=STATUS_STARTING,
                created_by=created_by,
                created_at=now,
                started_at=None,
                finished_at=None,
                stop_requested_at=None,
                error_message='',
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return self._serialize_run(run)

    def _run_loop(self, run_id: int, started_by: str) -> None:
        bot = None
        try:
            runtime_config, run_payload = self._build_runtime_config(run_id)
            bot = OptimizedCryptoBot(runtime_config)
            now = self._now_iso()
            timeframe_minutes = self._timeframe_to_minutes(run_payload['timeframe'])
            with self._lock:
                model = self._get_or_create_runtime()
                model.run_id = run_id
                model.trade_task_profile_id = run_payload['tradeTaskProfileId']
                model.profile_name = run_payload['profileName']
                model.status = STATUS_RUNNING
                model.started_at = model.started_at or now
                model.stopped_at = None
                model.stop_requested_at = None
                model.last_heartbeat_at = now
                model.last_cycle_started_at = None
                model.last_cycle_finished_at = None
                model.next_run_at = self._add_seconds(now, timeframe_minutes * 60)
                model.last_error = ''
                model.started_by = started_by
                model.symbol = run_payload['symbol']
                model.timeframe = run_payload['timeframe']
                model.timeframe_minutes = timeframe_minutes
                model.strategy_type = run_payload['strategyType']
                model.updated_at = now
                self._save_runtime(model)
                self._update_run_status(run_id, status=STATUS_RUNNING, started_at=now, error_message='')
                self._append_log(
                    run_id=run_id,
                    event_type='started',
                    status=model.status,
                    message='交易任务已启动',
                    detail={
                        'startedBy': started_by,
                        'profileName': run_payload['profileName'],
                        'symbol': run_payload['symbol'],
                        'timeframe': run_payload['timeframe'],
                        'strategyType': run_payload['strategyType'],
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
                        run_id=run_id,
                        event_type='cycle_started',
                        status=model.status,
                        message='开始新的交易周期',
                        detail={
                            'cycleStartedAt': cycle_started_at,
                            'profileName': model.profile_name,
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
                        run_id=run_id,
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
                self._update_run_status(run_id, status=STATUS_STOPPED, finished_at=stopped_at)
                self._append_log(
                    run_id=run_id,
                    event_type='stopped',
                    status=model.status,
                    message='交易任务已停止',
                    detail={
                        'stoppedAt': stopped_at,
                    },
                )
        except ConfigValidationError as exc:
            self._mark_failed(STATUS_CONFIG_ERROR, str(exc), run_id)
        except Exception as exc:
            logging.exception('交易任务运行失败: %s', exc)
            self._mark_failed(STATUS_FAILED, str(exc), run_id)
        finally:
            if bot is not None:
                bot.close()
            with self._lock:
                self._thread = None
                self._stop_event = Event()

    def _build_runtime_config(self, run_id: int) -> tuple[Config, dict[str, Any]]:
        with self.Session() as session:
            run = session.get(TradeTaskRunModel, run_id)
            if run is None:
                raise NotFoundError('交易任务运行快照不存在')
            run_payload = self._serialize_run(run)
        config_data = copy.deepcopy(self.config.config)
        app_cfg = dict(config_data.get('app') or {})
        trade_cfg = dict(app_cfg.get('trade') or {})
        strategy_cfg = dict(trade_cfg.get('strategy') or {})
        strategy_params = run_payload['strategyParams']
        strategy_cfg['type'] = run_payload['strategyType']
        strategy_cfg[run_payload['strategyType']] = strategy_params
        trade_cfg['sandbox_trade'] = bool(run_payload['sandboxTrade'])
        trade_cfg['symbol'] = run_payload['symbol']
        trade_cfg['timeframe'] = self._timeframe_to_minutes(run_payload['timeframe'])
        trade_cfg['limit'] = int(run_payload['tradeLimit'])
        trade_cfg['strategy'] = strategy_cfg
        app_cfg['trade'] = trade_cfg
        config_data['app'] = app_cfg
        return Config.from_dict(config_data), run_payload

    def _wrap_status_payload(self, runtime: dict[str, Any]) -> dict[str, Any]:
        payload = dict(runtime)
        payload['recentLogs'] = self.list_logs(limit=DEFAULT_LOG_LIMIT, run_id=payload.get('runId'))
        payload['currentRun'] = self.get_run_detail(payload['runId']) if payload.get('runId') else None
        return payload

    def _update_run_status(
        self,
        run_id: int,
        *,
        status: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        stop_requested_at: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self.Session() as session:
            model = session.get(TradeTaskRunModel, run_id)
            if model is None:
                return
            if status is not None:
                model.status = status
            if started_at is not None:
                model.started_at = started_at
            if finished_at is not None:
                model.finished_at = finished_at
            if stop_requested_at is not None:
                model.stop_requested_at = stop_requested_at
            if error_message is not None:
                model.error_message = error_message
            session.commit()

    def _mark_failed(self, status: str, error_message: str, run_id: int | None) -> None:
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
            if run_id:
                self._update_run_status(run_id, status=status, finished_at=now, error_message=error_message)
            self._append_log(
                run_id=run_id,
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
        if model.run_id:
            self._update_run_status(model.run_id, status=STATUS_STALE, finished_at=now, error_message=model.last_error)
        self._append_log(
            run_id=model.run_id,
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
                    run_id=None,
                    trade_task_profile_id=None,
                    profile_name=None,
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
                    timeframe=None,
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
            model.run_id = runtime.run_id
            model.trade_task_profile_id = runtime.trade_task_profile_id
            model.profile_name = runtime.profile_name
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
            model.timeframe = runtime.timeframe
            model.timeframe_minutes = runtime.timeframe_minutes
            model.strategy_type = runtime.strategy_type
            model.updated_at = runtime.updated_at
            session.commit()

    @staticmethod
    def _clone_model(model: TradeTaskRuntimeModel) -> TradeTaskRuntimeModel:
        return TradeTaskRuntimeModel(
            runner_name=model.runner_name,
            run_id=model.run_id,
            trade_task_profile_id=model.trade_task_profile_id,
            profile_name=model.profile_name,
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
            timeframe=model.timeframe,
            timeframe_minutes=model.timeframe_minutes,
            strategy_type=model.strategy_type,
            updated_at=model.updated_at,
        )

    def _serialize_runtime(self, model: TradeTaskRuntimeModel) -> dict[str, Any]:
        is_running = model.status in ACTIVE_STATUSES and self._is_thread_active()
        return {
            'runnerName': model.runner_name,
            'runId': model.run_id,
            'tradeTaskProfileId': model.trade_task_profile_id,
            'profileName': model.profile_name or '',
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
            'timeframe': model.timeframe or '',
            'timeframeMinutes': model.timeframe_minutes,
            'strategyType': model.strategy_type or '',
            'updatedAt': model.updated_at,
        }

    def _serialize_profile(
        self,
        model: TradeTaskProfileModel,
        strategy_profile: StrategyProfileModel | None,
    ) -> dict[str, Any]:
        return {
            'id': model.id,
            'name': model.name,
            'description': model.description or '',
            'enabled': bool(model.enabled),
            'strategyProfileId': model.strategy_profile_id,
            'strategyProfileName': strategy_profile.name if strategy_profile is not None else '',
            'strategyType': model.strategy_type,
            'symbol': model.symbol,
            'timeframe': model.timeframe,
            'sandboxTrade': bool(model.sandbox_trade),
            'tradeLimit': model.trade_limit,
            'runnerName': model.runner_name,
            'createdAt': model.created_at,
            'updatedAt': model.updated_at,
        }

    @staticmethod
    def _serialize_run(model: TradeTaskRunModel) -> dict[str, Any]:
        return {
            'id': model.id,
            'runnerName': model.runner_name,
            'tradeTaskProfileId': model.trade_task_profile_id,
            'profileName': model.profile_name,
            'strategyProfileId': model.strategy_profile_id,
            'strategyType': model.strategy_type,
            'strategySchemaVersion': model.strategy_schema_version,
            'symbol': model.symbol,
            'timeframe': model.timeframe,
            'sandboxTrade': bool(model.sandbox_trade),
            'tradeLimit': model.trade_limit,
            'strategyParams': json.loads(model.strategy_params_json or '{}'),
            'snapshot': json.loads(model.snapshot_json or '{}'),
            'status': model.status,
            'createdBy': model.created_by,
            'createdAt': model.created_at,
            'startedAt': model.started_at,
            'finishedAt': model.finished_at,
            'stopRequestedAt': model.stop_requested_at,
            'errorMessage': model.error_message or '',
        }

    def _append_log(self, run_id: int | None, event_type: str, status: str, message: str, detail: dict[str, Any] | None = None) -> None:
        now = self._now_iso()
        with self.Session() as session:
            session.add(
                TradeTaskLogModel(
                    run_id=run_id,
                    runner_name=DEFAULT_RUNNER_NAME,
                    event_type=event_type,
                    status=status,
                    message=message,
                    detail_json=json.dumps(detail or {}, ensure_ascii=False),
                    created_at=now,
                )
            )
            session.commit()

    def _serialize_logs(self, session, models: list[TradeTaskLogModel]) -> list[dict[str, Any]]:
        run_ids = [model.run_id for model in models if model.run_id is not None]
        runs = {}
        if run_ids:
            run_models = session.query(TradeTaskRunModel).filter(TradeTaskRunModel.id.in_(run_ids)).all()
            runs = {item.id: item for item in run_models}
        return [self._serialize_log(model, runs.get(model.run_id)) for model in models]

    @staticmethod
    def _serialize_log(model: TradeTaskLogModel, run: TradeTaskRunModel | None = None) -> dict[str, Any]:
        return {
            'id': model.id,
            'runId': model.run_id,
            'profileName': run.profile_name if run is not None else '',
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
                'run_id': 'INTEGER',
                'trade_task_profile_id': 'INTEGER',
                'profile_name': 'VARCHAR',
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
                'timeframe': 'VARCHAR',
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
                'run_id': 'INTEGER',
                'detail_json': 'TEXT',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            if missing_columns:
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_logs ADD COLUMN {name} {ddl}'))

    def _normalize_timeframe(self, timeframe: str) -> str:
        supported_timeframes = [str(item).strip() for item in self.config.backtest_config.get('supported_timeframes') or []]
        if timeframe in supported_timeframes:
            return timeframe
        if timeframe.isdigit() and int(timeframe) > 0:
            candidate = f'{int(timeframe)}m'
            if not supported_timeframes or candidate in supported_timeframes:
                return candidate
        raise ValidationError('周期不合法，请选择系统支持的周期')

    @staticmethod
    def _timeframe_to_minutes(timeframe: str) -> int:
        normalized = str(timeframe or '').strip().lower()
        if normalized.endswith('m') and normalized[:-1].isdigit():
            return int(normalized[:-1])
        if normalized.endswith('h') and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 60
        if normalized.endswith('d') and normalized[:-1].isdigit():
            return int(normalized[:-1]) * 24 * 60
        if normalized.isdigit():
            return int(normalized)
        raise ValidationError('周期格式不支持，当前仅支持 m / h / d')

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _add_seconds(value: str, seconds: int) -> str:
        return (datetime.fromisoformat(value) + timedelta(seconds=seconds)).isoformat()
