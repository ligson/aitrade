import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import create_engine
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from .trade_store_models import Base
from .trade_store_models import PositionStateModel
from .trade_store_models import TradeRecordModel


class SQLAlchemyTradeStore:
    def __init__(self, database_url: str):
        self.database_url = database_url
        url = make_url(database_url)
        self.backend = url.get_backend_name()
        self._ensure_parent_dir(url)
        self.engine = create_engine(database_url, pool_pre_ping=self.backend != 'sqlite')
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def insert_trade_record(self, record: Dict[str, Any]) -> int:
        payload = {
            'created_at': record.get('created_at') or self._utc_now(),
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
            'result': record.get('result', 'unknown'),
            'result_reason': record.get('result_reason'),
            'order_id': record.get('order_id'),
            'order_status': record.get('order_status'),
            'order_type': record.get('order_type'),
            'order_price': record.get('order_price'),
            'order_amount': record.get('order_amount'),
            'order_cost': record.get('order_cost'),
            'error_message': record.get('error_message'),
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

    def upsert_position_state(self, symbol: str, position: Dict[str, Any], source_trade_id: Optional[int] = None) -> None:
        with self.Session() as session:
            model = session.get(PositionStateModel, symbol)
            if model is None:
                model = PositionStateModel(symbol=symbol, updated_at=self._utc_now())
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

    def delete_position_state(self, symbol: str) -> None:
        with self.Session() as session:
            model = session.get(PositionStateModel, symbol)
            if model is not None:
                session.delete(model)
                session.commit()

    def get_position_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self.Session() as session:
            model = session.get(PositionStateModel, symbol)
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
    ) -> List[Dict[str, Any]]:
        stmt = select(TradeRecordModel).order_by(desc(TradeRecordModel.created_at)).limit(limit)
        if strategy:
            stmt = stmt.where(TradeRecordModel.strategy == strategy)
        if side:
            stmt = stmt.where(TradeRecordModel.side == side)
        if result:
            stmt = stmt.where(TradeRecordModel.result == result)
        if results:
            stmt = stmt.where(TradeRecordModel.result.in_(list(results)))
        with self.Session() as session:
            models = session.execute(stmt).scalars().all()
            return [self._trade_record_to_dict(model) for model in models]

    def query_position_states(self) -> List[Dict[str, Any]]:
        stmt = select(PositionStateModel).order_by(desc(PositionStateModel.updated_at))
        with self.Session() as session:
            models = session.execute(stmt).scalars().all()
            return [self._position_state_to_dict(model) for model in models]

    def _ensure_parent_dir(self, url) -> None:
        if url.get_backend_name() != 'sqlite':
            return
        database = url.database
        if not database or database == ':memory:':
            return
        db_path = os.path.abspath(database)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    def _trade_record_to_dict(self, model: TradeRecordModel) -> Dict[str, Any]:
        return {
            'id': model.id,
            'created_at': model.created_at,
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
            'result': model.result,
            'result_reason': model.result_reason,
            'order_id': model.order_id,
            'order_status': model.order_status,
            'order_type': model.order_type,
            'order_price': model.order_price,
            'order_amount': model.order_amount,
            'order_cost': model.order_cost,
            'error_message': model.error_message,
            'signal_meta': self._json_value(model.signal_meta_json, {}),
            'risk_snapshot': self._json_value(model.risk_snapshot_json, {}),
            'position_before': self._json_value(model.position_before_json),
            'position_after': self._json_value(model.position_after_json),
            'order_raw': self._json_value(model.order_raw_json, {}),
        }

    def _position_state_to_dict(self, model: PositionStateModel) -> Dict[str, Any]:
        return {
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

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
