from typing import Optional

from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class TradeTaskRuntimeModel(Base):
    __tablename__ = 'trade_task_runtime'
    __table_args__ = (
        Index('idx_trade_task_runtime_status_updated_at', 'status', 'updated_at'),
    )

    runner_name: Mapped[str] = mapped_column(String, primary_key=True)
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
    timeframe_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    strategy_type: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
