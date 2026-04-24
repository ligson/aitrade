from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Thread
from typing import Any

from fastapi import UploadFile

from ....config.config_file import Config
from ....db import BacktestJobModel
from ....db import BacktestTradeModel
from ....db import StrategyProfileModel
from ....db import Base
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.backtest.data_service import BacktestDataService
from ...exceptions import NotFoundError
from ...exceptions import ValidationError


class BacktestService:
    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        backtest_runtime_config = dict(config.backtest_config)
        backtest_runtime_config['proxy_enable'] = config.proxy_enable
        backtest_runtime_config['proxy_url'] = config.proxy_url
        self.data_service = BacktestDataService(backtest_runtime_config)
        Base.metadata.create_all(self.engine)

    def get_data_options(self) -> dict[str, Any]:
        return self.data_service.get_data_options()

    def get_data_status(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        pair = str(payload.get('symbol') or self.config.backtest_config['default_symbol']).strip()
        timeframe = str(payload.get('timeframe') or self.config.backtest_config['default_timeframe']).strip()
        data_dir = self.data_service.ensure_data_dir(self.config.backtest_config)
        status = self.data_service.get_data_status(pair=pair, timeframe=timeframe, timerange=self.config.backtest_config['download_timerange'])
        status['dataDir'] = data_dir
        status['userDataDir'] = str(self.data_service.freqtrade.user_data_dir)
        return status

    def page_data_catalog(self, symbol: str, timeframe: str, keyword: str, offset: int, size: int) -> tuple[int, list[dict[str, Any]]]:
        rows = self.data_service.list_data_files(symbol=symbol.strip(), timeframe=timeframe.strip(), keyword=keyword.strip())
        total = len(rows)
        return total, rows[offset: offset + size]

    def download_data(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        pair = str(payload.get('symbol') or self.config.backtest_config['default_symbol']).strip()
        timeframe = str(payload.get('timeframe') or self.config.backtest_config['default_timeframe']).strip()
        self.data_service.ensure_data_dir(self.config.backtest_config)
        try:
            return self.data_service.download_data(pair=pair, timeframe=timeframe, timerange=self.config.backtest_config['download_timerange'])
        except RuntimeError as exc:
            raise ValidationError(str(exc)) from exc

    def export_data_archive(self, filenames: list[str]) -> tuple[str, bytes]:
        return self.data_service.export_data_files(filenames)

    async def import_data_archive(self, upload_file: UploadFile, overwrite: bool = False) -> dict[str, Any]:
        if upload_file.filename is None or not upload_file.filename.lower().endswith('.zip'):
            raise ValidationError('历史数据导入仅支持 zip 压缩包')
        content = await upload_file.read()
        if not content:
            raise ValidationError('上传的历史数据压缩包不能为空')
        return self.data_service.import_data_archive(content, overwrite=overwrite)

    def delete_data_file(self, filename: str) -> dict[str, Any]:
        self.data_service.delete_data_file(filename)
        return {'deleted': True, 'filename': filename}

    def create_job(self, payload: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        strategy_profile_id = int(payload.get('strategyProfileId') or 0)
        if strategy_profile_id <= 0:
            raise ValidationError('请选择策略配置')
        initial_balance = float(payload.get('initialBalance') or 10000)
        fee_rate = float(payload.get('feeRate') or 0.001)
        if initial_balance <= 0:
            raise ValidationError('初始资金必须大于 0')
        if fee_rate < 0:
            raise ValidationError('手续费率不能小于 0')

        data_file = str(payload.get('dataFile') or '').strip()
        if data_file:
            file_info = self.data_service.inspect_data_file(data_file)
            symbol = file_info['symbol']
            timeframe = file_info['timeframe']
            timerange_from = file_info['timerangeFrom']
            timerange_to = file_info['timerangeTo']
            data_source = {
                'sourceType': 'file',
                'filename': file_info['filename'],
                'path': file_info['path'],
                'symbol': symbol,
                'timeframe': timeframe,
                'format': file_info['format'],
                'size': file_info['size'],
                'timerangeFrom': timerange_from,
                'timerangeTo': timerange_to,
            }
        else:
            timerange, timerange_from, timerange_to = self.data_service.extract_timerange(
                payload,
                fallback=self.config.backtest_config['download_timerange'],
            )
            symbol = str(payload.get('symbol') or self.config.backtest_config['default_symbol']).strip()
            timeframe = str(payload.get('timeframe') or self.config.backtest_config['default_timeframe']).strip()
            data_source = {
                'sourceType': 'legacy',
                'symbol': symbol,
                'timeframe': timeframe,
                'timerange': timerange,
            }
            data_file = ''

        with self.Session() as session:
            profile = session.get(StrategyProfileModel, strategy_profile_id)
            if profile is None:
                raise NotFoundError('策略配置不存在')
            params = json.loads(profile.params_json)
            now = datetime.now(timezone.utc).isoformat()
            status = 'pending' if profile.strategy_type == 'btc_spot_breakout' else 'unsupported'
            error_message = '' if status == 'pending' else '当前仅支持 btc_spot_breakout 策略离线回测'
            job = BacktestJobModel(
                strategy_type=profile.strategy_type,
                strategy_profile_id=profile.id,
                profile_name=profile.name,
                symbol=symbol,
                timeframe=timeframe,
                timerange_from=timerange_from,
                timerange_to=timerange_to,
                status=status,
                initial_balance=initial_balance,
                fee_rate=fee_rate,
                summary_json=json.dumps({}, ensure_ascii=False),
                params_json=json.dumps(params, ensure_ascii=False),
                data_source_json=json.dumps(data_source, ensure_ascii=False),
                error_message=error_message,
                created_by=str(current_user.get('username') or current_user.get('nickname') or current_user.get('id')),
                created_at=now,
                started_at=None,
                finished_at=now if status == 'unsupported' else None,
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            job_id = job.id

        if status == 'pending':
            thread = Thread(target=self._run_job, args=(job_id,), daemon=True)
            thread.start()
        return self.get_job_detail(job_id)

    def _run_job(self, job_id: int) -> None:
        with self.Session() as session:
            job = session.get(BacktestJobModel, job_id)
            if job is None:
                return
            job.status = 'running'
            job.started_at = datetime.now(timezone.utc).isoformat()
            session.commit()
            strategy_type = job.strategy_type
            symbol = job.symbol
            timeframe = job.timeframe
            timerange_from = job.timerange_from
            timerange_to = job.timerange_to
            params = json.loads(job.params_json)
            data_source = json.loads(job.data_source_json or '{}')
            data_file = str(data_source.get('filename') or '').strip() if isinstance(data_source, dict) else ''
            initial_balance = float(job.initial_balance)
            fee_rate = float(job.fee_rate)

        try:
            result = self.data_service.run_backtest(
                strategy_type=strategy_type,
                symbol=symbol,
                timeframe=timeframe,
                timerange_from=timerange_from,
                timerange_to=timerange_to,
                strategy_params=params,
                initial_balance=initial_balance,
                fee_rate=fee_rate,
                data_file=data_file or None,
            )
            with self.Session() as session:
                job = session.get(BacktestJobModel, job_id)
                if job is None:
                    return
                session.query(BacktestTradeModel).filter(BacktestTradeModel.job_id == job_id).delete()
                now = datetime.now(timezone.utc).isoformat()
                for item in result['trades']:
                    session.add(
                        BacktestTradeModel(
                            job_id=job_id,
                            bar_time=item['barTime'],
                            side=item['side'],
                            price=float(item['price']),
                            quantity=float(item['quantity']),
                            fee=float(item['fee']),
                            pnl=None if item.get('pnl') is None else float(item['pnl']),
                            reason=str(item.get('reason') or ''),
                            signal_json=json.dumps(item.get('signal') or {}, ensure_ascii=False),
                            position_json=json.dumps(item.get('position') or {}, ensure_ascii=False),
                            created_at=item.get('createdAt') or now,
                        )
                    )
                job.summary_json = json.dumps(result['summary'], ensure_ascii=False)
                job.data_source_json = json.dumps(result.get('dataSource') or {}, ensure_ascii=False)
                job.error_message = ''
                job.status = 'success'
                job.finished_at = now
                session.commit()
        except Exception as exc:
            with self.Session() as session:
                job = session.get(BacktestJobModel, job_id)
                if job is None:
                    return
                job.status = 'failed'
                job.error_message = str(exc)
                job.finished_at = datetime.now(timezone.utc).isoformat()
                session.commit()

    def page_jobs(self, offset: int, size: int, keyword: str = '', status: str = '') -> tuple[int, list[dict[str, Any]]]:
        with self.Session() as session:
            query = session.query(BacktestJobModel)
            if keyword.strip():
                like_value = f'%{keyword.strip()}%'
                query = query.filter(
                    (BacktestJobModel.profile_name.like(like_value))
                    | (BacktestJobModel.symbol.like(like_value))
                    | (BacktestJobModel.strategy_type.like(like_value))
                )
            if status.strip():
                query = query.filter(BacktestJobModel.status == status.strip())
            total = query.count()
            models = query.order_by(BacktestJobModel.id.desc()).offset(offset).limit(size).all()
            rows = [self._serialize_job(model) for model in models]
            return total, rows

    def get_job_detail(self, job_id: int) -> dict[str, Any]:
        with self.Session() as session:
            model = session.get(BacktestJobModel, job_id)
            if model is None:
                raise NotFoundError('回测任务不存在')
            return self._serialize_job(model)

    def page_job_trades(self, job_id: int, offset: int, size: int) -> tuple[int, list[dict[str, Any]]]:
        with self.Session() as session:
            job = session.get(BacktestJobModel, job_id)
            if job is None:
                raise NotFoundError('回测任务不存在')
            query = session.query(BacktestTradeModel).filter(BacktestTradeModel.job_id == job_id)
            total = query.count()
            models = query.order_by(BacktestTradeModel.id.asc()).offset(offset).limit(size).all()
            rows = [
                {
                    'id': item.id,
                    'jobId': item.job_id,
                    'barTime': item.bar_time,
                    'side': item.side,
                    'price': item.price,
                    'quantity': item.quantity,
                    'fee': item.fee,
                    'pnl': item.pnl,
                    'reason': item.reason,
                    'signal': json.loads(item.signal_json or '{}'),
                    'position': json.loads(item.position_json or '{}'),
                    'createdAt': item.created_at,
                }
                for item in models
            ]
            return total, rows

    @staticmethod
    def _serialize_job(model: BacktestJobModel) -> dict[str, Any]:
        return {
            'id': model.id,
            'strategyType': model.strategy_type,
            'strategyProfileId': model.strategy_profile_id,
            'profileName': model.profile_name,
            'symbol': model.symbol,
            'timeframe': model.timeframe,
            'timerangeFrom': model.timerange_from,
            'timerangeTo': model.timerange_to,
            'status': model.status,
            'initialBalance': model.initial_balance,
            'feeRate': model.fee_rate,
            'summary': json.loads(model.summary_json or '{}'),
            'params': json.loads(model.params_json or '{}'),
            'dataSource': json.loads(model.data_source_json or '{}'),
            'errorMessage': model.error_message or '',
            'createdBy': model.created_by,
            'createdAt': model.created_at,
            'startedAt': model.started_at,
            'finishedAt': model.finished_at,
        }
