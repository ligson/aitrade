from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class TradeTaskProfileModel(Base):
    __tablename__ = 'trade_task_profiles'
    __table_args__ = (
        Index('idx_trade_task_profiles_runner_enabled', 'runner_name', 'enabled'),
        Index('idx_trade_task_profiles_strategy_profile', 'strategy_profile_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    strategy_profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    sandbox_trade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trade_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    runner_name: Mapped[str] = mapped_column(String, nullable=False, default='default')
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class TradeTaskRunModel(Base):
    __tablename__ = 'trade_task_runs'
    __table_args__ = (
        Index('idx_trade_task_runs_runner_status_created_at', 'runner_name', 'status', 'created_at'),
        Index('idx_trade_task_runs_profile_created_at', 'trade_task_profile_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    runner_name: Mapped[str] = mapped_column(String, nullable=False)
    trade_task_profile_id: Mapped[Optional[int]] = mapped_column(Integer)
    profile_name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_profile_id: Mapped[Optional[int]] = mapped_column(Integer)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    strategy_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    sandbox_trade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trade_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_params_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(String)
    finished_at: Mapped[Optional[str]] = mapped_column(String)
    stop_requested_at: Mapped[Optional[str]] = mapped_column(String)
    error_message: Mapped[Optional[str]] = mapped_column(Text)


class TradeTaskRuntimeModel(Base):
    __tablename__ = 'trade_task_runtime'
    __table_args__ = (
        Index('idx_trade_task_runtime_status_updated_at', 'status', 'updated_at'),
    )

    runner_name: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[Optional[int]] = mapped_column(Integer)
    trade_task_profile_id: Mapped[Optional[int]] = mapped_column(Integer)
    profile_name: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[Optional[str]] = mapped_column(String)
    stopped_at: Mapped[Optional[str]] = mapped_column(String)
    stop_requested_at: Mapped[Optional[str]] = mapped_column(String)
    last_heartbeat_at: Mapped[Optional[str]] = mapped_column(String)
    last_cycle_started_at: Mapped[Optional[str]] = mapped_column(String)
    last_cycle_finished_at: Mapped[Optional[str]] = mapped_column(String)
    next_run_at: Mapped[Optional[str]] = mapped_column(String)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    started_by: Mapped[Optional[str]] = mapped_column(String)
    symbol: Mapped[Optional[str]] = mapped_column(String)
    timeframe: Mapped[Optional[str]] = mapped_column(String)
    timeframe_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    strategy_type: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
