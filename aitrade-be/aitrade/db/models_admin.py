from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from .base import Base


class UserModel(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_users_username', 'username', unique=True),
        Index('idx_users_email', 'email', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    remark: Mapped[str] = mapped_column(Text, default='')
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default='active')
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    last_login_at: Mapped[Optional[str]] = mapped_column(String)


class CaptchaSessionModel(Base):
    __tablename__ = 'captcha_sessions'

    captcha_key: Mapped[str] = mapped_column(String, primary_key=True)
    captcha_code: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class StrategyProfileModel(Base):
    __tablename__ = 'strategy_profiles'
    __table_args__ = (
        Index('idx_strategy_profiles_type', 'strategy_type'),
        Index('idx_strategy_profiles_enabled', 'enabled'),
        Index('idx_strategy_profiles_owner_created_at', 'owner_user_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class SignalSourceProfileModel(Base):
    __tablename__ = 'signal_source_profiles'
    __table_args__ = (
        Index('idx_signal_source_profiles_type', 'source_type'),
        Index('idx_signal_source_profiles_enabled', 'enabled'),
        Index('idx_signal_source_profiles_owner_created_at', 'owner_user_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class SystemSettingProfileModel(Base):
    __tablename__ = 'system_setting_profiles'
    __table_args__ = (
        Index('idx_system_setting_profiles_enabled', 'enabled'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class UserExchangeSettingModel(Base):
    __tablename__ = 'user_exchange_settings'
    __table_args__ = (
        Index('idx_user_exchange_settings_owner', 'owner_user_id', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exchange_type: Mapped[str] = mapped_column(String, nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default='')
    api_secret: Mapped[str] = mapped_column(Text, nullable=False, default='')
    password: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
