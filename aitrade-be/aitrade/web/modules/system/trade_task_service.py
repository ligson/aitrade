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
from ....db import SignalSourceProfileModel
from ....db import StrategyProfileModel
from ....db import TradeTaskLogModel
from ....db import TradeTaskProfileModel
from ....db import TradeTaskRunModel
from ....db import TradeTaskRuntimeModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.strategies.fusion_profile import build_fusion_runtime_params
from ....trade.strategies.fusion_profile import normalize_fusion_strategy_profile_config
from ....trade.strategies.fusion_profile import summarize_fusion_strategy_profile_config
from ....trade.strategies.registry import get_strategy_definition
from ....trade.trade import OptimizedCryptoBot
from ....trade.trading_system.trade_executor import TradingHaltError
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ..strategies.params import normalize_strategy_params
from .service import SystemService

STATUS_STOPPED = 'stopped'
STATUS_STARTING = 'starting'
STATUS_RUNNING = 'running'
STATUS_STOP_REQUESTED = 'stop_requested'
STATUS_FAILED = 'failed'
STATUS_CONFIG_ERROR = 'config_error'
STATUS_STALE = 'stale'
# starting/running/stop_requested 表示当前 runner 仍应被视为活跃态；
# stale 表示数据库残留了活跃状态，但当前 Web 进程里已经没有对应线程。
ACTIVE_STATUSES = {STATUS_STARTING, STATUS_RUNNING, STATUS_STOP_REQUESTED}
DEFAULT_RUNNER_NAME = 'default'
DEFAULT_LOG_LIMIT = 20
TRADE_MODES = {'live', 'sandbox', 'paper'}


class TradeTaskService:
    """维护交易任务配置档案、运行快照、运行时状态和事件日志。"""
    _instances: dict[str, 'TradeTaskService'] = {}
    _instances_lock = Lock()

    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        self.system_service = SystemService(config)
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
                logging.info('创建新的交易任务服务实例')
                instance = cls(config)
                cls._instances[database_url] = instance
            else:
                logging.debug('复用已有交易任务服务实例')
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
        fee_rate = self._normalize_non_negative_float(payload.get('feeRate'), '手续费率')
        slippage_rate = self._normalize_non_negative_float(payload.get('slippageRate'), '滑点率')
        daily_loss_stop_enabled = self._normalize_bool(payload.get('dailyLossStopEnabled'), '是否启用单日亏损停机')
        daily_loss_stop_threshold = self._normalize_non_negative_float(payload.get('dailyLossStopThreshold'), '单日亏损停机阈值')
        if daily_loss_stop_enabled and daily_loss_stop_threshold <= 0:
            raise ValidationError('启用单日亏损停机时，阈值必须大于 0')
        runner_name = str(payload.get('runnerName') or DEFAULT_RUNNER_NAME).strip() or DEFAULT_RUNNER_NAME
        if runner_name != DEFAULT_RUNNER_NAME:
            raise ValidationError('当前仅支持 default runner')
        enabled = bool(payload.get('enabled', True))
        description = str(payload.get('description') or '').strip()
        trade_mode = self._normalize_trade_mode_payload(payload)
        sandbox_trade = trade_mode == 'sandbox'
        profile_id = payload.get('id')
        now = self._now_iso()

        with self.Session() as session:
            strategy_profile = session.get(StrategyProfileModel, strategy_profile_id)
            if strategy_profile is None:
                raise NotFoundError('策略配置不存在')
            if not strategy_profile.enabled:
                raise ValidationError('所选策略配置已停用')
            if strategy_profile.strategy_type == 'btc_spot_trend_breakout' and timeframe != '1h':
                raise ValidationError('BTC 现货趋势突破策略的交易任务周期当前固定为 1h')
            if strategy_profile.strategy_type == 'spot_multi_signal_fusion':
                definition = get_strategy_definition(strategy_profile.strategy_type)
                normalized_params = normalize_strategy_params(definition, json.loads(strategy_profile.params_json or '{}'))
                fusion_summary = summarize_fusion_strategy_profile_config(normalized_params)
                if fusion_summary['requires1hTimeframe'] and timeframe != '1h':
                    raise ValidationError('现货多源融合策略包含固定 1h 的趋势突破节点时，交易任务周期当前固定为 1h')

            if profile_id is None:
                logging.info(
                    '创建交易任务配置: name=%s symbol=%s timeframe=%s strategy_profile_id=%s trade_mode=%s',
                    name,
                    symbol,
                    timeframe,
                    strategy_profile_id,
                    trade_mode,
                )
                model = TradeTaskProfileModel(
                    name=name,
                    description=description,
                    enabled=enabled,
                    strategy_profile_id=strategy_profile.id,
                    strategy_type=strategy_profile.strategy_type,
                    symbol=symbol,
                    timeframe=timeframe,
                    sandbox_trade=sandbox_trade,
                    trade_mode=trade_mode,
                    trade_limit=trade_limit,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    daily_loss_stop_enabled=daily_loss_stop_enabled,
                    daily_loss_stop_threshold=daily_loss_stop_threshold,
                    runner_name=runner_name,
                    created_at=now,
                    updated_at=now,
                )
                session.add(model)
                session.commit()
                session.refresh(model)
            else:
                logging.info(
                    '更新交易任务配置: id=%s name=%s symbol=%s timeframe=%s strategy_profile_id=%s trade_mode=%s',
                    profile_id,
                    name,
                    symbol,
                    timeframe,
                    strategy_profile_id,
                    trade_mode,
                )
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
                model.trade_mode = trade_mode
                model.trade_limit = trade_limit
                model.fee_rate = fee_rate
                model.slippage_rate = slippage_rate
                model.daily_loss_stop_enabled = daily_loss_stop_enabled
                model.daily_loss_stop_threshold = daily_loss_stop_threshold
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
                logging.warning('拒绝删除运行中的交易任务配置: profile_id=%s runtime_status=%s', profile_id, runtime.status)
                raise ValidationError('当前交易任务正在使用该配置，不能删除')
            logging.info('删除交易任务配置: profile_id=%s name=%s', model.id, model.name)
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
        # 启动前先固化 run snapshot，再把 runtime 切到 starting，最后才真正起线程；
        # 这样即便后续页面继续修改配置，也不会回溯影响本次已经启动的任务。
        with self._lock:
            model = self._get_or_create_runtime()
            if self._is_thread_active():
                logging.warning('交易任务已在运行，忽略重复启动请求: run_id=%s status=%s', model.run_id, model.status)
                return self._wrap_status_payload(self._serialize_runtime(model))
            if model.status in ACTIVE_STATUSES:
                logging.warning('检测到活跃状态残留，启动前先标记 stale: run_id=%s status=%s', model.run_id, model.status)
                self._mark_stale_runtime(model)
                model = self._get_or_create_runtime()

            run = self._create_run_snapshot(trade_task_profile_id, current_user)
            now = self._now_iso()
            started_by = run['createdBy']
            logging.info(
                '开始启动交易任务: run_id=%s profile=%s symbol=%s timeframe=%s strategy_type=%s',
                run['id'],
                run['profileName'],
                run['symbol'],
                run['timeframe'],
                run['strategyType'],
            )
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
        # stop_requested 只是通知循环在合适的边界退出，真正 stopped 需要等待运行线程收尾完成。
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
            logging.info('收到停止交易任务请求: run_id=%s status=%s', model.run_id, model.status)
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
        # run snapshot 会在启动前固化 profile、策略参数和任务级输入，
        # 后续 profile 或系统设置再变更时，当前 run 仍按启动瞬间的快照继续执行。
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
            trade_mode = self._normalize_trade_mode_value(profile.trade_mode, bool(profile.sandbox_trade))
            runtime_defaults_snapshot = self.system_service.get_runtime_default_snapshots()
            fusion_config_snapshot = None
            kline_node_snapshots: list[dict[str, Any]] = []
            signal_source_snapshots: list[dict[str, Any]] = []
            if strategy_profile.strategy_type == 'spot_multi_signal_fusion':
                fusion_config_snapshot = normalize_fusion_strategy_profile_config(normalized_params)
                kline_node_snapshots = self._build_kline_node_snapshots(session, fusion_config_snapshot)
                signal_source_snapshots = self._build_signal_source_snapshots(
                    session,
                    fusion_config_snapshot,
                    runtime_defaults_snapshot,
                    profile.timeframe,
                )
            snapshot = {
                'profileId': profile.id,
                'profileName': profile.name,
                'runnerName': profile.runner_name,
                'strategyProfileId': strategy_profile.id,
                'strategyProfileName': strategy_profile.name,
                'strategyType': strategy_profile.strategy_type,
                'strategySchemaVersion': definition['schemaVersion'],
                'strategyParams': normalized_params,
                'strategyDefinitionSnapshot': {
                    'strategyType': definition['strategyType'],
                    'displayName': definition['displayName'],
                    'description': definition['description'],
                    'strategyCategory': definition.get('strategyCategory'),
                    'configMode': definition.get('configMode'),
                    'usableAsFusionNode': bool(definition.get('usableAsFusionNode', False)),
                    'supportsSpot': bool(definition.get('supportsSpot', True)),
                    'supportsPaper': bool(definition.get('supportsPaper', True)),
                    'supportsBacktest': bool(definition.get('supportsBacktest', False)),
                    'fixedConstraints': list(definition.get('fixedConstraints') or []),
                    'schemaVersion': definition['schemaVersion'],
                },
                'strategyProfileSnapshot': {
                    'id': strategy_profile.id,
                    'name': strategy_profile.name,
                    'description': strategy_profile.description,
                    'enabled': bool(strategy_profile.enabled),
                    'strategyType': strategy_profile.strategy_type,
                    'schemaVersion': strategy_profile.schema_version,
                },
                'fusionConfigSnapshot': fusion_config_snapshot,
                'klineNodeSnapshots': kline_node_snapshots,
                'signalSourceSnapshots': signal_source_snapshots,
                'systemDefaultsSnapshot': runtime_defaults_snapshot,
                'symbol': profile.symbol,
                'timeframe': profile.timeframe,
                'tradeMode': trade_mode,
                'sandboxTrade': trade_mode == 'sandbox',
                'tradeLimit': int(profile.trade_limit),
                'marketFeeds': {
                    'tradeFlow': dict(runtime_defaults_snapshot.get('tradeFlow') or {}),
                },
                'execution': {
                    'feeRate': float(profile.fee_rate),
                    'slippageRate': float(profile.slippage_rate),
                    'dailyLossStopEnabled': bool(profile.daily_loss_stop_enabled),
                    'dailyLossStopThreshold': float(profile.daily_loss_stop_threshold),
                },
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
                sandbox_trade=trade_mode == 'sandbox',
                trade_mode=trade_mode,
                trade_limit=int(profile.trade_limit),
                fee_rate=float(profile.fee_rate),
                slippage_rate=float(profile.slippage_rate),
                daily_loss_stop_enabled=bool(profile.daily_loss_stop_enabled),
                daily_loss_stop_threshold=float(profile.daily_loss_stop_threshold),
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
            logging.info(
                '交易任务运行快照创建完成: run_id=%s profile=%s symbol=%s timeframe=%s strategy_type=%s',
                run.id,
                run.profile_name,
                run.symbol,
                run.timeframe,
                run.strategy_type,
            )
            return self._serialize_run(run)

    def _run_loop(self, run_id: int, started_by: str) -> None:
        bot = None
        try:
            # 先把系统级生效配置与任务快照拼成当前运行时配置，再创建真实 bot 实例。
            runtime_config, run_payload = self._build_runtime_config(run_id)
            bot = OptimizedCryptoBot(
                runtime_config,
                execution_context={
                    'run_id': run_id,
                    'trade_task_profile_id': run_payload['tradeTaskProfileId'],
                },
            )
            now = self._now_iso()
            timeframe_minutes = self._timeframe_to_minutes(run_payload['timeframe'])
            logging.info('交易任务运行线程已启动: run_id=%s timeframe_minutes=%s', run_id, timeframe_minutes)
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
                # 每轮开始前先刷新 heartbeat 和周期开始时间，便于页面和日志观察当前活跃度。
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

                # 周期结束后写回下一次计划执行时间；如果已经收到停止请求，则保留 stop_requested 状态等待退出。
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
            logging.info('交易任务运行线程准备结束: run_id=%s', run_id)
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
        except TradingHaltError as exc:
            logging.warning('交易任务触发风控停机: run_id=%s reason=%s detail=%s', run_id, exc.reason, exc.detail)
            self._mark_risk_halted(run_id, exc)
        except ConfigValidationError as exc:
            logging.error('交易任务运行配置校验失败: run_id=%s error=%s', run_id, exc)
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
        # 运行中的 bot 使用的是“系统级生效配置 + 本次 run snapshot”的组合结果；
        # 因此系统设置会影响未来新任务，但不会改写已经启动任务的任务级参数。
        with self.Session() as session:
            run = session.get(TradeTaskRunModel, run_id)
            if run is None:
                raise NotFoundError('交易任务运行快照不存在')
            run_payload = self._serialize_run(run)
        snapshot = dict(run_payload.get('snapshot') or {})
        config_data = self.system_service.build_effective_config_dict()
        app_cfg = dict(config_data.get('app') or {})
        trade_cfg = dict(app_cfg.get('trade') or {})
        strategy_cfg = dict(trade_cfg.get('strategy') or {})
        strategy_params = run_payload['strategyParams']
        if run_payload['strategyType'] == 'spot_multi_signal_fusion':
            strategy_params = build_fusion_runtime_params(
                snapshot.get('fusionConfigSnapshot') or strategy_params,
                list(snapshot.get('klineNodeSnapshots') or []),
                list(snapshot.get('signalSourceSnapshots') or []),
            )
        strategy_cfg['type'] = run_payload['strategyType']
        strategy_cfg[run_payload['strategyType']] = strategy_params
        trade_cfg['trade_mode'] = run_payload['tradeMode']
        trade_cfg['sandbox_trade'] = run_payload['tradeMode'] == 'sandbox'
        trade_cfg['symbol'] = run_payload['symbol']
        trade_cfg['timeframe'] = self._timeframe_to_minutes(run_payload['timeframe'])
        trade_cfg['limit'] = int(run_payload['tradeLimit'])
        trade_cfg['strategy'] = strategy_cfg
        execution_snapshot = dict(snapshot.get('execution') or {})
        trade_cfg['execution'] = {
            'fee_rate': float(execution_snapshot.get('feeRate', run_payload['feeRate'])),
            'slippage_rate': float(execution_snapshot.get('slippageRate', run_payload['slippageRate'])),
            'daily_loss_stop_enabled': bool(execution_snapshot.get('dailyLossStopEnabled', run_payload['dailyLossStopEnabled'])),
            'daily_loss_stop_threshold': float(execution_snapshot.get('dailyLossStopThreshold', run_payload['dailyLossStopThreshold'])),
        }
        market_feeds_snapshot = dict(snapshot.get('marketFeeds') or {})
        trade_flow_snapshot = dict(market_feeds_snapshot.get('tradeFlow') or {})
        trade_cfg['market_feeds'] = {
            'trade_flow': {
                'enabled': bool(trade_flow_snapshot.get('enabled', True)),
                'freshness_seconds': int(trade_flow_snapshot.get('freshnessSeconds', 120) or 120),
                'lookback_trades': int(trade_flow_snapshot.get('lookbackTrades', 200) or 200),
            },
        }
        persistence_cfg = dict(trade_cfg.get('persistence') or {})
        persistence_cfg['execution'] = dict(trade_cfg['execution'])
        trade_cfg['persistence'] = persistence_cfg
        app_cfg['trade'] = trade_cfg
        config_data['app'] = app_cfg
        logging.debug(
            '构建交易任务运行配置: run_id=%s strategy_type=%s symbol=%s timeframe=%s strategy_param_keys=%s trade_flow_enabled=%s',
            run_id,
            run_payload['strategyType'],
            run_payload['symbol'],
            run_payload['timeframe'],
            list(strategy_params.keys()),
            trade_cfg['market_feeds']['trade_flow']['enabled'],
        )
        return Config.from_dict(config_data), run_payload

    def _build_kline_node_snapshots(self, session, fusion_config: dict[str, Any]) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for item in list(fusion_config.get('klineNodes') or []):
            if not bool(item.get('enabled', True)):
                continue
            node_type = str(item.get('nodeType') or 'strategy_profile')
            if node_type == 'builtin_technical':
                snapshots.append({
                    'nodeType': 'builtin_technical',
                    'strategyProfileId': None,
                    'strategyType': 'builtin_technical',
                    'name': str(item.get('name') or '技术面节点'),
                    'enabled': True,
                    'weight': float(item.get('weight', 0.5)),
                    'params': dict(item.get('params') or {}),
                    'requires_1h_timeframe': False,
                })
                continue
            strategy_profile_id = item.get('strategyProfileId')
            if not strategy_profile_id:
                raise ValidationError('融合策略 K 线节点缺少 strategyProfileId')
            profile = session.get(StrategyProfileModel, int(strategy_profile_id))
            if profile is None:
                raise NotFoundError(f'融合策略引用的 K 线策略配置不存在: {strategy_profile_id}')
            if not profile.enabled:
                raise ValidationError(f'融合策略引用的 K 线策略配置已停用: {profile.name}')
            definition = get_strategy_definition(profile.strategy_type)
            if not bool(definition.get('usableAsFusionNode', False)):
                raise ValidationError(f'策略 {profile.name} 当前不能作为融合节点')
            profile_params = normalize_strategy_params(definition, json.loads(profile.params_json or '{}'))
            snapshots.append({
                'nodeType': 'strategy_profile',
                'strategyProfileId': profile.id,
                'strategyType': profile.strategy_type,
                'name': str(item.get('name') or profile.name),
                'enabled': True,
                'weight': float(item.get('weight', 0.5)),
                'params': profile_params,
                'schemaVersion': profile.schema_version,
                'description': profile.description,
                'requires_1h_timeframe': profile.strategy_type == 'btc_spot_trend_breakout',
            })
        return snapshots

    def _build_signal_source_snapshots(
        self,
        session,
        fusion_config: dict[str, Any],
        runtime_defaults: dict[str, Any],
        trade_task_timeframe: str,
    ) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        indicator_source_count = 0
        for item in list(fusion_config.get('signalSourceNodes') or []):
            if not bool(item.get('enabled', True)):
                continue
            source_profile_id = item.get('signalSourceProfileId')
            if not source_profile_id:
                raise ValidationError('融合策略信号源节点缺少 signalSourceProfileId')
            profile = session.get(SignalSourceProfileModel, int(source_profile_id))
            if profile is None:
                raise NotFoundError(f'融合策略引用的信号源配置不存在: {source_profile_id}')
            if not profile.enabled:
                raise ValidationError(f'融合策略引用的信号源配置已停用: {profile.name}')
            params = json.loads(profile.params_json or '{}')
            merged_params = dict(params)
            if profile.source_type == 'trade_flow':
                merged_params = {
                    'freshness_seconds': int((runtime_defaults.get('tradeFlow') or {}).get('freshnessSeconds', 120)),
                    'lookback_trades': int((runtime_defaults.get('tradeFlow') or {}).get('lookbackTrades', 200)),
                    **params,
                    **dict(item.get('params') or {}),
                }
            elif profile.source_type == 'indicator':
                indicator_source_count += 1
                if indicator_source_count > 1:
                    raise ValidationError('融合策略第一阶段最多只能启用一个 indicator 信号源节点')
                merged_params = self._normalize_indicator_source_params(
                    {
                        **params,
                        **dict(item.get('params') or {}),
                    },
                    trade_task_timeframe,
                    profile.name,
                )
            snapshots.append({
                'signalSourceProfileId': profile.id,
                'sourceType': profile.source_type,
                'name': str(item.get('name') or profile.name),
                'enabled': True,
                'required': bool(item.get('required', False)),
                'weight': float(item.get('weight', 0.4)),
                'thresholds': dict(item.get('thresholds') or {}),
                'params': merged_params,
                'schemaVersion': profile.schema_version,
                'description': profile.description,
            })
        return snapshots

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
            logging.error('标记交易任务失败: run_id=%s status=%s error=%s', run_id, status, error_message)
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

    def _mark_risk_halted(self, run_id: int | None, exc: TradingHaltError) -> None:
        now = self._now_iso()
        detail = dict(exc.detail or {})
        detail.setdefault('reason', exc.reason)
        detail.setdefault('stoppedAt', now)
        with self._lock:
            model = self._get_or_create_runtime()
            model.status = STATUS_STOPPED
            model.stopped_at = now
            model.next_run_at = None
            model.last_heartbeat_at = now
            model.last_error = ''
            model.updated_at = now
            self._save_runtime(model)
            if run_id:
                self._update_run_status(run_id, status=STATUS_STOPPED, finished_at=now, error_message='')
            self._append_log(
                run_id=run_id,
                event_type='risk_halt_triggered',
                status=model.status,
                message='触发单日亏损停机，交易任务已停止',
                detail=detail,
            )

    def _mark_stale_if_needed(self) -> None:
        with self._lock:
            model = self._get_or_create_runtime()
            if model.status in ACTIVE_STATUSES and not self._is_thread_active():
                self._mark_stale_runtime(model)

    def _mark_stale_runtime(self, model: TradeTaskRuntimeModel) -> dict[str, Any]:
        # stale 表示数据库里还残留活跃状态，但当前 Web 进程内已没有对应运行线程。
        now = self._now_iso()
        logging.warning('标记交易任务为 stale: run_id=%s previous_status=%s', model.run_id, model.status)
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
        trade_mode = self._normalize_trade_mode_value(model.trade_mode, bool(model.sandbox_trade))
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
            'tradeMode': trade_mode,
            'sandboxTrade': trade_mode == 'sandbox',
            'tradeLimit': model.trade_limit,
            'feeRate': float(model.fee_rate),
            'slippageRate': float(model.slippage_rate),
            'dailyLossStopEnabled': bool(model.daily_loss_stop_enabled),
            'dailyLossStopThreshold': float(model.daily_loss_stop_threshold),
            'runnerName': model.runner_name,
            'createdAt': model.created_at,
            'updatedAt': model.updated_at,
        }

    @staticmethod
    def _serialize_run(model: TradeTaskRunModel) -> dict[str, Any]:
        trade_mode = TradeTaskService._normalize_trade_mode_value(model.trade_mode, bool(model.sandbox_trade))
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
            'tradeMode': trade_mode,
            'sandboxTrade': trade_mode == 'sandbox',
            'tradeLimit': model.trade_limit,
            'feeRate': float(model.fee_rate),
            'slippageRate': float(model.slippage_rate),
            'dailyLossStopEnabled': bool(model.daily_loss_stop_enabled),
            'dailyLossStopThreshold': float(model.daily_loss_stop_threshold),
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
        # 这里做的是轻量历史兼容补列，避免旧库缺少运行时字段时直接阻断 Web 管理台启动。
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
                logging.info('检测到 trade_task_runtime 缺少历史字段，自动补列: columns=%s', list(missing_columns.keys()))
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
                logging.info('检测到 trade_task_logs 缺少历史字段，自动补列: columns=%s', list(missing_columns.keys()))
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_logs ADD COLUMN {name} {ddl}'))

        if 'trade_task_profiles' in inspector.get_table_names():
            columns = {column['name'] for column in inspector.get_columns('trade_task_profiles')}
            column_definitions = {
                'trade_mode': "VARCHAR DEFAULT 'sandbox'",
                'fee_rate': 'FLOAT DEFAULT 0',
                'slippage_rate': 'FLOAT DEFAULT 0',
                'daily_loss_stop_enabled': 'BOOLEAN DEFAULT 0',
                'daily_loss_stop_threshold': 'FLOAT DEFAULT 0',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            if missing_columns:
                logging.info('检测到 trade_task_profiles 缺少历史字段，自动补列: columns=%s', list(missing_columns.keys()))
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_profiles ADD COLUMN {name} {ddl}'))

        if 'trade_task_runs' in inspector.get_table_names():
            columns = {column['name'] for column in inspector.get_columns('trade_task_runs')}
            column_definitions = {
                'trade_mode': "VARCHAR DEFAULT 'sandbox'",
                'fee_rate': 'FLOAT DEFAULT 0',
                'slippage_rate': 'FLOAT DEFAULT 0',
                'daily_loss_stop_enabled': 'BOOLEAN DEFAULT 0',
                'daily_loss_stop_threshold': 'FLOAT DEFAULT 0',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            if missing_columns:
                logging.info('检测到 trade_task_runs 缺少历史字段，自动补列: columns=%s', list(missing_columns.keys()))
                with self.engine.begin() as connection:
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_task_runs ADD COLUMN {name} {ddl}'))

    def _normalize_indicator_source_params(
        self,
        params: dict[str, Any],
        trade_task_timeframe: str,
        profile_name: str,
    ) -> dict[str, Any]:
        indicator_key = str(params.get('indicator_key') or '').strip().lower()
        if indicator_key not in {'rsi', 'macd'}:
            raise ValidationError(
                f'指标信号源 {profile_name} 当前仅支持 rsi 或 macd，收到: {indicator_key or "空值"}'
            )
        indicator_timeframe = self._normalize_timeframe(str(params.get('primary_timeframe') or '').strip())
        if self._timeframe_to_minutes(indicator_timeframe) != self._timeframe_to_minutes(trade_task_timeframe):
            raise ValidationError(
                f'指标信号源 {profile_name} 的主周期必须与交易任务周期一致: signal_source={indicator_timeframe} task={trade_task_timeframe}'
            )
        lookback_candles = int(params.get('lookback_candles') or 0)
        period = int(params.get('period') or 0)
        lower_threshold = float(params.get('lower_threshold') or 0)
        upper_threshold = float(params.get('upper_threshold') or 0)
        breakout_lookback = int(params.get('breakout_lookback') or 0)
        volume_multiplier = float(params.get('volume_multiplier') or 0)
        if lookback_candles <= 0:
            raise ValidationError(f'指标信号源 {profile_name} 的回看K线数必须大于 0')
        if period <= 1:
            raise ValidationError(f'指标信号源 {profile_name} 的指标周期必须大于 1')
        if lookback_candles < period + 5:
            raise ValidationError(f'指标信号源 {profile_name} 的回看K线数至少要比指标周期多 5 根')
        if lower_threshold < 0 or lower_threshold > 100:
            raise ValidationError(f'指标信号源 {profile_name} 的低阈值必须在 0 到 100 之间')
        if upper_threshold < 0 or upper_threshold > 100:
            raise ValidationError(f'指标信号源 {profile_name} 的高阈值必须在 0 到 100 之间')
        if lower_threshold >= upper_threshold:
            raise ValidationError(f'指标信号源 {profile_name} 的低阈值必须小于高阈值')
        if breakout_lookback <= 1:
            raise ValidationError(f'指标信号源 {profile_name} 的突破回看窗口必须大于 1')
        if volume_multiplier <= 0:
            raise ValidationError(f'指标信号源 {profile_name} 的放量倍率必须大于 0')
        return {
            **params,
            'indicator_key': indicator_key,
            'primary_timeframe': trade_task_timeframe,
            'lookback_candles': lookback_candles,
            'period': period,
            'lower_threshold': lower_threshold,
            'upper_threshold': upper_threshold,
            'confirm_crossover': bool(params.get('confirm_crossover', True)),
            'breakout_lookback': breakout_lookback,
            'volume_multiplier': volume_multiplier,
        }

    @staticmethod
    def _normalize_trade_mode_value(trade_mode: str | None, sandbox_trade: bool = True) -> str:
        normalized = str(trade_mode or '').strip().lower()
        if normalized in TRADE_MODES:
            return normalized
        return 'sandbox' if sandbox_trade else 'live'

    def _normalize_trade_mode_payload(self, payload: dict[str, Any]) -> str:
        raw_trade_mode = payload.get('tradeMode')
        if raw_trade_mode is not None:
            normalized = str(raw_trade_mode).strip().lower()
            if normalized not in TRADE_MODES:
                raise ValidationError('交易方式只支持 live、sandbox 或 paper')
            return normalized
        return 'sandbox' if bool(payload.get('sandboxTrade', True)) else 'live'

    @staticmethod
    def _normalize_non_negative_float(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f'{label}必须是数字')
        normalized = float(value)
        if normalized < 0:
            raise ValidationError(f'{label}不能小于 0')
        return normalized

    @staticmethod
    def _normalize_bool(value: Any, label: str) -> bool:
        if not isinstance(value, bool):
            raise ValidationError(f'{label}必须是布尔值')
        return value

    def _normalize_timeframe(self, timeframe: str) -> str:
        # 页面侧通常使用 5m/15m/1h 等字符串周期；这里先按系统支持列表校验，再决定是否接受数字分钟写法。
        effective_config, _ = self.system_service.get_effective_config()
        supported_timeframes = [str(item).strip() for item in effective_config.backtest_config.get('supported_timeframes') or []]
        if timeframe in supported_timeframes:
            return timeframe
        if timeframe.isdigit() and int(timeframe) > 0:
            candidate = f'{int(timeframe)}m'
            if not supported_timeframes or candidate in supported_timeframes:
                return candidate
        raise ValidationError('周期不合法，请选择系统支持的周期')

    @staticmethod
    def _timeframe_to_minutes(timeframe: str) -> int:
        # Config 运行时仍使用整数分钟数，因此需要把页面和持久化里的字符串周期统一转换。
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
