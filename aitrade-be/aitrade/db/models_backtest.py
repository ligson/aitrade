from typing import Optional

from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class BacktestJobModel(Base):
    __tablename__ = 'backtest_jobs'
    __table_args__ = (
        Index('idx_backtest_jobs_status_created_at', 'status', 'created_at'),
        Index('idx_backtest_jobs_strategy_created_at', 'strategy_type', 'created_at'),
        Index('idx_backtest_jobs_profile_created_at', 'strategy_profile_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    strategy_profile_id: Mapped[Optional[int]] = mapped_column(Integer)
    profile_name: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    timerange_from: Mapped[str] = mapped_column(String, nullable=False)
    timerange_to: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    initial_balance: Mapped[float] = mapped_column(Float, nullable=False)
    fee_rate: Mapped[float] = mapped_column(Float, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    data_source_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(String)
    finished_at: Mapped[Optional[str]] = mapped_column(String)


class BacktestTradeModel(Base):
    __tablename__ = 'backtest_trades'
    __table_args__ = (
        Index('idx_backtest_trades_job_bar_time', 'job_id', 'bar_time'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('backtest_jobs.id', ondelete='CASCADE'), nullable=False)
    bar_time: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[Optional[float]] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    signal_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    position_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    created_at: Mapped[str] = mapped_column(String, nullable=False)
