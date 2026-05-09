import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import case
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.engine import make_url

from ...db import Base
from ...db import PositionStateModel
from ...db import TradeRecordModel
from ...db import TradeTaskProfileModel
from ...db import TradeTaskRunModel
from ...db import UserModel
from ...db.session import get_engine
from ...db.session import get_session_factory


class SQLAlchemyTradeStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        url = make_url(database_url)
        self.backend = url.get_backend_name()
        self.engine = get_engine(database_url)
        self.Session = get_session_factory(database_url)
        Base.metadata.create_all(self.engine)
        self._ensure_trade_records_schema()

    def close(self) -> None:
        return None

    def insert_trade_record(self, record: Dict[str, Any]) -> int:
        payload = {
            'owner_user_id': record.get('owner_user_id'),
            'created_at': record.get('created_at') or self._utc_now(),
            'run_id': record.get('run_id'),
            'trade_task_profile_id': record.get('trade_task_profile_id'),
            'symbol': record.get('symbol'),
            'strategy': record.get('strategy', 'unknown'),
            'trigger_source': record.get('trigger_source', 'strategy_signal'),
            'side': record.get('side', 'unknown'),
            'signal_confidence': record.get('signal_confidence'),
            'signal_reason': record.get('signal_reason'),
            'market_price': record.get('market_price'),
            'requested_amount': record.get('requested_amount'),
            'stop_loss_price': record.get('stop_loss_price'),
            'trailing_stop_price': record.get('trailing_stop_price'),
            'risk_per_trade': record.get('risk_per_trade'),
            'exchange_type': record.get('exchange_type', 'unknown'),
            'sandbox': bool(record.get('sandbox')),
            'trade_mode': record.get('trade_mode', 'sandbox' if record.get('sandbox') else 'live'),
            'result': record.get('result', 'unknown'),
            'result_reason': record.get('result_reason'),
            'order_id': record.get('order_id'),
            'order_status': record.get('order_status'),
            'order_type': record.get('order_type'),
            'order_price': record.get('order_price'),
            'order_amount': record.get('order_amount'),
            'order_cost': record.get('order_cost'),
            'fee_rate': record.get('fee_rate'),
            'slippage_rate': record.get('slippage_rate'),
            'estimated_fill_price': record.get('estimated_fill_price'),
            'estimated_fee': record.get('estimated_fee'),
            'realized_pnl': record.get('realized_pnl'),
            'realized_pnl_net': record.get('realized_pnl_net'),
            'error_message': record.get('error_message'),
            'daily_loss_snapshot_json': self._json_text(record.get('daily_loss_snapshot')),
            'signal_meta_json': self._json_text(record.get('signal_meta')),
            'risk_snapshot_json': self._json_text(record.get('risk_snapshot')),
            'position_before_json': self._json_text(record.get('position_before')),
            'position_after_json': self._json_text(record.get('position_after')),
            'order_raw_json': self._json_text(record.get('order_raw')),
        }
        model = TradeRecordModel(**payload)
        with self.Session() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return model.id

    def upsert_position_state(self, owner_user_id: int, symbol: str, position: Dict[str, Any], source_trade_id: Optional[int] = None) -> None:
        with self.Session() as session:
            model = session.get(PositionStateModel, (owner_user_id, symbol))
            if model is None:
                model = PositionStateModel(owner_user_id=owner_user_id, symbol=symbol, updated_at=self._utc_now())
                session.add(model)
            model.strategy = position.get('strategy')
            model.entry_time = position.get('entry_time')
            model.entry_price = position.get('entry_price')
            model.amount = position.get('amount')
            model.stop_loss = position.get('stop_loss')
            model.initial_stop_loss = position.get('initial_stop_loss')
            model.trailing_stop_price = position.get('trailing_stop_price')
            model.highest_price = position.get('highest_price')
            model.highest_close = position.get('highest_close')
            model.meta_json = self._json_text(position.get('meta', {}))
            model.source_trade_id = source_trade_id
            model.updated_at = self._utc_now()
            session.commit()

    def delete_position_state(self, owner_user_id: int, symbol: str) -> None:
        with self.Session() as session:
            model = session.get(PositionStateModel, (owner_user_id, symbol))
            if model is not None:
                session.delete(model)
                session.commit()

    def get_position_state(self, owner_user_id: int, symbol: str) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            model = session.get(PositionStateModel, (owner_user_id, symbol))
            if model is None:
                return None
            return self._position_state_to_dict(model)

    def query_trade_records(
        self,
        limit: int = 20,
        strategy: Optional[str] = None,
        side: Optional[str] = None,
        result: Optional[str] = None,
        results: Optional[Sequence[str]] = None,
        offset: int = 0,
        symbol: Optional[str] = None,
        run_id: Optional[int] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        owner_user_id: Optional[int] = None,
    ) -> list[Dict[str, Any]]:
        stmt = select(TradeRecordModel)
        stmt = self._apply_trade_filters(stmt, strategy, side, result, results, symbol, run_id, created_from, created_to, owner_user_id)
        stmt = stmt.order_by(desc(TradeRecordModel.created_at)).offset(offset).limit(limit)
        with self.Session() as session:
            models = session.execute(stmt).scalars().all()
            return [self._trade_record_to_dict(model) for model in models]

    def count_trade_records(
        self,
        strategy: Optional[str] = None,
        side: Optional[str] = None,
        result: Optional[str] = None,
        results: Optional[Sequence[str]] = None,
        symbol: Optional[str] = None,
        run_id: Optional[int] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        owner_user_id: Optional[int] = None,
    ) -> int:
        stmt = select(func.count()).select_from(TradeRecordModel)
        stmt = self._apply_trade_filters(stmt, strategy, side, result, results, symbol, run_id, created_from, created_to, owner_user_id)
        with self.Session() as session:
            return int(session.execute(stmt).scalar_one())

    def query_position_states(self, owner_user_id: Optional[int] = None) -> list[Dict[str, Any]]:
        stmt = select(PositionStateModel)
        if owner_user_id is not None:
            stmt = stmt.where(PositionStateModel.owner_user_id == owner_user_id)
        stmt = stmt.order_by(desc(PositionStateModel.updated_at))
        with self.Session() as session:
            models = session.execute(stmt).scalars().all()
            return [self._position_state_to_dict(model) for model in models]

    def get_daily_loss_summary(self, run_id: int, created_from: str, created_to: str) -> Dict[str, Any]:
        stmt = (
            select(
                func.coalesce(func.sum(TradeRecordModel.realized_pnl_net), 0.0),
                func.coalesce(
                    func.sum(
                        case(
                            (TradeRecordModel.realized_pnl_net < 0, -TradeRecordModel.realized_pnl_net),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ),
                func.count(),
            )
            .where(TradeRecordModel.run_id == run_id)
            .where(TradeRecordModel.result == 'executed')
            .where(TradeRecordModel.side == 'sell')
            .where(TradeRecordModel.created_at >= created_from)
            .where(TradeRecordModel.created_at < created_to)
        )
        with self.Session() as session:
            realized_pnl_net, realized_loss, trade_count = session.execute(stmt).one()
            return {
                'runId': run_id,
                'createdFrom': created_from,
                'createdTo': created_to,
                'realizedPnlNet': float(realized_pnl_net or 0.0),
                'realizedLoss': float(realized_loss or 0.0),
                'tradeCount': int(trade_count or 0),
            }

    def list_trade_symbols(self, owner_user_id: Optional[int] = None) -> list[str]:
        stmt = (
            select(TradeRecordModel.symbol)
            .where(TradeRecordModel.symbol.is_not(None))
            .where(func.trim(TradeRecordModel.symbol) != '')
        )
        if owner_user_id is not None:
            stmt = stmt.where(TradeRecordModel.owner_user_id == owner_user_id)
        stmt = stmt.distinct().order_by(TradeRecordModel.symbol.asc())
        with self.Session() as session:
            rows = session.execute(stmt).scalars().all()
            return [item.strip() for item in rows if isinstance(item, str) and item.strip()]

    @staticmethod
    def _apply_trade_filters(stmt, strategy, side, result, results, symbol, run_id, created_from, created_to, owner_user_id):
        if strategy:
            stmt = stmt.where(TradeRecordModel.strategy == strategy)
        if side:
            stmt = stmt.where(TradeRecordModel.side == side)
        if result:
            stmt = stmt.where(TradeRecordModel.result == result)
        if results:
            stmt = stmt.where(TradeRecordModel.result.in_(list(results)))
        if symbol:
            stmt = stmt.where(TradeRecordModel.symbol == symbol)
        if run_id is not None:
            stmt = stmt.where(TradeRecordModel.run_id == run_id)
        if created_from:
            stmt = stmt.where(TradeRecordModel.created_at >= created_from)
        if created_to:
            stmt = stmt.where(TradeRecordModel.created_at <= created_to)
        if owner_user_id is not None:
            stmt = stmt.where(TradeRecordModel.owner_user_id == owner_user_id)
        return stmt

    def _trade_record_to_dict(self, model: TradeRecordModel) -> Dict[str, Any]:
        return {
            'id': model.id,
            'owner_user_id': model.owner_user_id,
            'created_at': model.created_at,
            'run_id': model.run_id,
            'trade_task_profile_id': model.trade_task_profile_id,
            'symbol': model.symbol,
            'strategy': model.strategy,
            'trigger_source': model.trigger_source,
            'side': model.side,
            'signal_confidence': model.signal_confidence,
            'signal_reason': model.signal_reason,
            'market_price': model.market_price,
            'requested_amount': model.requested_amount,
            'stop_loss_price': model.stop_loss_price,
            'trailing_stop_price': model.trailing_stop_price,
            'risk_per_trade': model.risk_per_trade,
            'exchange_type': model.exchange_type,
            'sandbox': bool(model.sandbox),
            'trade_mode': model.trade_mode or ('sandbox' if model.sandbox else 'live'),
            'result': model.result,
            'result_reason': model.result_reason,
            'order_id': model.order_id,
            'order_status': model.order_status,
            'order_type': model.order_type,
            'order_price': model.order_price,
            'order_amount': model.order_amount,
            'order_cost': model.order_cost,
            'fee_rate': model.fee_rate,
            'slippage_rate': model.slippage_rate,
            'estimated_fill_price': model.estimated_fill_price,
            'estimated_fee': model.estimated_fee,
            'realized_pnl': model.realized_pnl,
            'realized_pnl_net': model.realized_pnl_net,
            'error_message': model.error_message,
            'daily_loss_snapshot': self._json_value(model.daily_loss_snapshot_json),
            'signal_meta': self._json_value(model.signal_meta_json, {}),
            'risk_snapshot': self._json_value(model.risk_snapshot_json, {}),
            'position_before': self._json_value(model.position_before_json),
            'position_after': self._json_value(model.position_after_json),
            'order_raw': self._json_value(model.order_raw_json, {}),
        }

    def _position_state_to_dict(self, model: PositionStateModel) -> Dict[str, Any]:
        return {
            'owner_user_id': model.owner_user_id,
            'symbol': model.symbol,
            'strategy': model.strategy,
            'entry_time': model.entry_time,
            'entry_price': model.entry_price,
            'amount': model.amount,
            'stop_loss': model.stop_loss,
            'initial_stop_loss': model.initial_stop_loss,
            'trailing_stop_price': model.trailing_stop_price,
            'highest_price': model.highest_price,
            'highest_close': model.highest_close,
            'meta': self._json_value(model.meta_json, {}),
            'source_trade_id': model.source_trade_id,
            'updated_at': model.updated_at,
        }

    @staticmethod
    def _json_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _json_value(value: Optional[str], default: Any = None) -> Any:
        if value is None:
            return default
        return json.loads(value)

    def _ensure_trade_records_schema(self) -> None:
        inspector = inspect(self.engine)
        table_names = set(inspector.get_table_names())
        fallback_owner_user_id = self._get_primary_admin_user_id()

        if 'trade_records' in table_names:
            columns = {column['name'] for column in inspector.get_columns('trade_records')}
            column_definitions = {
                'owner_user_id': 'INTEGER',
                'run_id': 'INTEGER',
                'trade_task_profile_id': 'INTEGER',
                'trade_mode': "VARCHAR DEFAULT 'sandbox'",
                'fee_rate': 'FLOAT',
                'slippage_rate': 'FLOAT',
                'estimated_fill_price': 'FLOAT',
                'estimated_fee': 'FLOAT',
                'realized_pnl': 'FLOAT',
                'realized_pnl_net': 'FLOAT',
                'daily_loss_snapshot_json': 'TEXT',
            }
            missing_columns = {name: ddl for name, ddl in column_definitions.items() if name not in columns}
            with self.engine.begin() as connection:
                if missing_columns:
                    logging.info('检测到 trade_records 缺少历史字段，自动补列: columns=%s', list(missing_columns.keys()))
                    for name, ddl in missing_columns.items():
                        connection.execute(text(f'ALTER TABLE trade_records ADD COLUMN {name} {ddl}'))
                connection.execute(
                    text(
                        'UPDATE trade_records SET owner_user_id = COALESCE(owner_user_id, (SELECT owner_user_id FROM trade_task_profiles WHERE trade_task_profiles.id = trade_records.trade_task_profile_id), (SELECT owner_user_id FROM trade_task_runs WHERE trade_task_runs.id = trade_records.run_id), :owner_user_id) WHERE owner_user_id IS NULL'
                    ),
                    {'owner_user_id': fallback_owner_user_id},
                )
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_trade_records_run_created_at ON trade_records (run_id, created_at)'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_trade_records_profile_created_at ON trade_records (trade_task_profile_id, created_at)'))
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_trade_records_owner_created_at ON trade_records (owner_user_id, created_at)'))

        self._ensure_position_state_schema(fallback_owner_user_id)

    def _ensure_position_state_schema(self, fallback_owner_user_id: int | None) -> None:
        inspector = inspect(self.engine)
        if 'position_state' not in inspector.get_table_names():
            return
        columns = {column['name'] for column in inspector.get_columns('position_state')}
        pk_columns = list((inspector.get_pk_constraint('position_state') or {}).get('constrained_columns') or [])
        legacy_owner_user_id = int(fallback_owner_user_id or 0)

        if 'owner_user_id' in columns and set(pk_columns) == {'owner_user_id', 'symbol'}:
            with self.engine.begin() as connection:
                if fallback_owner_user_id is not None:
                    connection.execute(
                        text('UPDATE position_state SET owner_user_id = :owner_user_id WHERE owner_user_id = 0'),
                        {'owner_user_id': fallback_owner_user_id},
                    )
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_position_state_owner_updated_at ON position_state (owner_user_id, updated_at)'))
            return

        if self.backend != 'sqlite':
            with self.engine.begin() as connection:
                if 'owner_user_id' not in columns:
                    logging.warning('非 SQLite 存储暂不支持自动重建 position_state 主键，仅补列 owner_user_id')
                    connection.execute(text('ALTER TABLE position_state ADD COLUMN owner_user_id INTEGER'))
                connection.execute(
                    text('UPDATE position_state SET owner_user_id = COALESCE(owner_user_id, :owner_user_id) WHERE owner_user_id IS NULL'),
                    {'owner_user_id': legacy_owner_user_id},
                )
                connection.execute(text('CREATE INDEX IF NOT EXISTS idx_position_state_owner_updated_at ON position_state (owner_user_id, updated_at)'))
            return

        legacy_table_name = 'position_state_legacy_owner_migration'
        logging.info('检测到 position_state 仍为旧版全局结构，开始升级为 owner 维度表')
        with self.engine.begin() as connection:
            connection.execute(text(f'DROP TABLE IF EXISTS {legacy_table_name}'))
            connection.execute(text(f'ALTER TABLE position_state RENAME TO {legacy_table_name}'))
        PositionStateModel.__table__.create(bind=self.engine, checkfirst=True)
        legacy_columns = {column['name'] for column in inspect(self.engine).get_columns(legacy_table_name)}
        owner_expr = 'owner_user_id' if 'owner_user_id' in legacy_columns else str(legacy_owner_user_id)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    f'''
                    INSERT INTO position_state (
                        owner_user_id,
                        symbol,
                        strategy,
                        entry_time,
                        entry_price,
                        amount,
                        stop_loss,
                        initial_stop_loss,
                        trailing_stop_price,
                        highest_price,
                        highest_close,
                        meta_json,
                        source_trade_id,
                        updated_at
                    )
                    SELECT
                        COALESCE({owner_expr}, :owner_user_id),
                        symbol,
                        strategy,
                        entry_time,
                        entry_price,
                        amount,
                        stop_loss,
                        initial_stop_loss,
                        trailing_stop_price,
                        highest_price,
                        highest_close,
                        meta_json,
                        source_trade_id,
                        updated_at
                    FROM {legacy_table_name}
                    '''
                ),
                {'owner_user_id': legacy_owner_user_id},
            )
            if fallback_owner_user_id is not None:
                connection.execute(
                    text('UPDATE position_state SET owner_user_id = :owner_user_id WHERE owner_user_id = 0'),
                    {'owner_user_id': fallback_owner_user_id},
                )
            connection.execute(text('DROP TABLE position_state_legacy_owner_migration'))
            connection.execute(text('CREATE INDEX IF NOT EXISTS idx_position_state_owner_updated_at ON position_state (owner_user_id, updated_at)'))

    def _get_primary_admin_user_id(self) -> int | None:
        with self.Session() as session:
            model = session.query(UserModel).filter(UserModel.is_admin.is_(True)).order_by(UserModel.id.asc()).first()
            if model is not None:
                return int(model.id)
            model = session.query(TradeTaskProfileModel).filter(TradeTaskProfileModel.owner_user_id.is_not(None)).order_by(TradeTaskProfileModel.owner_user_id.asc()).first()
            if model is not None and model.owner_user_id is not None:
                return int(model.owner_user_id)
            model = session.query(TradeTaskRunModel).filter(TradeTaskRunModel.owner_user_id.is_not(None)).order_by(TradeTaskRunModel.owner_user_id.asc()).first()
            if model is not None and model.owner_user_id is not None:
                return int(model.owner_user_id)
            return None

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
