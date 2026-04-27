from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class TradeTaskLogModel(Base):
    __tablename__ = 'trade_task_logs'
    __table_args__ = (
        Index('idx_trade_task_logs_runner_created_at', 'runner_name', 'created_at'),
        Index('idx_trade_task_logs_event_created_at', 'event_type', 'created_at'),
        Index('idx_trade_task_logs_run_created_at', 'run_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(Integer)
    runner_name: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')
    created_at: Mapped[str] = mapped_column(String, nullable=False)
