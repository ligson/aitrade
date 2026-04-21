from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import Float
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class TradeRecordModel(Base):
    __tablename__ = 'trade_records'
    __table_args__ = (
        Index('idx_trade_records_created_at', 'created_at'),
        Index('idx_trade_records_strategy_created_at', 'strategy', 'created_at'),
        Index('idx_trade_records_symbol_created_at', 'symbol', 'created_at'),
        Index('idx_trade_records_result_created_at', 'result', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    strategy: Mapped[str] = mapped_column(String, nullable=False)
    trigger_source: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    signal_confidence: Mapped[Optional[float]] = mapped_column(Float)
    signal_reason: Mapped[Optional[str]] = mapped_column(Text)
    market_price: Mapped[Optional[float]] = mapped_column(Float)
    requested_amount: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss_price: Mapped[Optional[float]] = mapped_column(Float)
    trailing_stop_price: Mapped[Optional[float]] = mapped_column(Float)
    risk_per_trade: Mapped[Optional[float]] = mapped_column(Float)
    exchange_type: Mapped[str] = mapped_column(String, nullable=False)
    sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result: Mapped[str] = mapped_column(String, nullable=False)
    result_reason: Mapped[Optional[str]] = mapped_column(Text)
    order_id: Mapped[Optional[str]] = mapped_column(String)
    order_status: Mapped[Optional[str]] = mapped_column(String)
    order_type: Mapped[Optional[str]] = mapped_column(String)
    order_price: Mapped[Optional[float]] = mapped_column(Float)
    order_amount: Mapped[Optional[float]] = mapped_column(Float)
    order_cost: Mapped[Optional[float]] = mapped_column(Float)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    signal_meta_json: Mapped[Optional[str]] = mapped_column(Text)
    risk_snapshot_json: Mapped[Optional[str]] = mapped_column(Text)
    position_before_json: Mapped[Optional[str]] = mapped_column(Text)
    position_after_json: Mapped[Optional[str]] = mapped_column(Text)
    order_raw_json: Mapped[Optional[str]] = mapped_column(Text)


class PositionStateModel(Base):
    __tablename__ = 'position_state'

    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    strategy: Mapped[Optional[str]] = mapped_column(String)
    entry_time: Mapped[Optional[str]] = mapped_column(String)
    entry_price: Mapped[Optional[float]] = mapped_column(Float)
    amount: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    initial_stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    trailing_stop_price: Mapped[Optional[float]] = mapped_column(Float)
    highest_price: Mapped[Optional[float]] = mapped_column(Float)
    highest_close: Mapped[Optional[float]] = mapped_column(Float)
    meta_json: Mapped[Optional[str]] = mapped_column(Text)
    source_trade_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
