from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ....config.config_file import Config
from ....db import Base
from ....db import UserExchangeSettingModel
from ....db import UserModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from .service import SystemService

SUPPORTED_EXCHANGE_TYPES = {'binance', 'okx'}


class UserExchangeService:
    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        Base.metadata.create_all(self.engine)

    def get_settings(self, current_user: dict[str, Any]) -> dict[str, Any]:
        owner_user_id = int(current_user.get('id') or 0)
        if owner_user_id <= 0:
            raise ValidationError('当前用户信息无效')
        with self.Session() as session:
            user = session.get(UserModel, owner_user_id)
            if user is None:
                raise NotFoundError('用户不存在')
            model = session.query(UserExchangeSettingModel).filter(UserExchangeSettingModel.owner_user_id == owner_user_id).first()
            return self._serialize_settings(model, user)

    def save_settings(self, payload: dict[str, Any], current_user: dict[str, Any]) -> dict[str, Any]:
        owner_user_id = int(current_user.get('id') or 0)
        if owner_user_id <= 0:
            raise ValidationError('当前用户信息无效')
        editable = payload.get('editable')
        if not isinstance(editable, dict):
            raise ValidationError('交易所配置内容不能为空')
        with self.Session() as session:
            user = session.get(UserModel, owner_user_id)
            if user is None:
                raise NotFoundError('用户不存在')
            model = session.query(UserExchangeSettingModel).filter(UserExchangeSettingModel.owner_user_id == owner_user_id).first()
            normalized = self._normalize_editable_settings(editable, model)
            now = self._now_iso()
            if model is None:
                model = UserExchangeSettingModel(
                    owner_user_id=owner_user_id,
                    exchange_type=normalized['exchange_type'],
                    api_key=normalized['api_key'],
                    api_secret=normalized['api_secret'],
                    password=normalized['password'],
                    created_at=now,
                    updated_at=now,
                )
                session.add(model)
            else:
                model.exchange_type = normalized['exchange_type']
                model.api_key = normalized['api_key']
                model.api_secret = normalized['api_secret']
                model.password = normalized['password']
                model.updated_at = now
            session.commit()
            session.refresh(model)
            logging.info('保存用户交易所配置: owner_user_id=%s exchange_type=%s has_password=%s', owner_user_id, model.exchange_type, bool(model.password.strip()))
            return self._serialize_settings(model, user)

    def build_runtime_exchange_config(self, owner_user_id: int) -> dict[str, str]:
        with self.Session() as session:
            model = session.query(UserExchangeSettingModel).filter(UserExchangeSettingModel.owner_user_id == owner_user_id).first()
        if model is None:
            raise ValidationError('当前用户尚未在“交易所设置”页配置交易所凭证')
        return self._validate_runtime_exchange_config({
            'type': model.exchange_type,
            'api_key': model.api_key,
            'api_secret': model.api_secret,
            'password': model.password,
        })

    def _serialize_settings(self, model: UserExchangeSettingModel | None, user: UserModel) -> dict[str, Any]:
        system_service = SystemService(self.config)
        api_key = str(model.api_key if model is not None else '').strip()
        api_secret = str(model.api_secret if model is not None else '').strip()
        password = str(model.password if model is not None else '').strip()
        exchange_type = str(model.exchange_type if model is not None else '').strip()
        return {
            'editable': {
                'exchangeType': exchange_type,
                'apiKey': system_service._mask_secret(api_key),
                'apiSecret': system_service._mask_secret(api_secret),
                'password': system_service._mask_secret(password),
                'hasApiKey': bool(api_key),
                'hasApiSecret': bool(api_secret),
                'hasPassword': bool(password),
                'apiKeyMasked': system_service._mask_secret(api_key),
                'apiSecretMasked': system_service._mask_secret(api_secret),
                'passwordMasked': system_service._mask_secret(password),
            },
            'meta': {
                'userId': user.id,
                'username': user.username,
                'nickname': user.nickname,
                'isAdmin': bool(user.is_admin),
                'updatedAt': model.updated_at if model is not None else None,
            },
        }

    def _normalize_editable_settings(self, editable: dict[str, Any], model: UserExchangeSettingModel | None) -> dict[str, str]:
        exchange_type = str(editable.get('exchangeType') or '').strip().lower()
        if exchange_type not in SUPPORTED_EXCHANGE_TYPES:
            raise ValidationError('交易所类型仅支持 binance 或 okx')
        existing_api_key = str(model.api_key if model is not None else '').strip()
        existing_api_secret = str(model.api_secret if model is not None else '').strip()
        existing_password = str(model.password if model is not None else '').strip()
        api_key = self._resolve_secret_field(str(editable.get('apiKey') or '').strip(), existing_api_key)
        api_secret = self._resolve_secret_field(str(editable.get('apiSecret') or '').strip(), existing_api_secret)
        password = self._resolve_secret_field(str(editable.get('password') or '').strip(), existing_password)
        if not api_key:
            raise ValidationError('API Key 不能为空')
        if not api_secret:
            raise ValidationError('API Secret 不能为空')
        if exchange_type == 'okx' and not password:
            raise ValidationError('使用 OKX 时，Password 不能为空')
        if exchange_type != 'okx':
            password = ''
        return {
            'exchange_type': exchange_type,
            'api_key': api_key,
            'api_secret': api_secret,
            'password': password,
        }

    def _resolve_secret_field(self, raw_value: str, existing_value: str) -> str:
        masked_existing = SystemService._mask_secret(existing_value)
        if raw_value in {'', '********', masked_existing}:
            return existing_value
        return raw_value

    def _validate_runtime_exchange_config(self, payload: dict[str, Any]) -> dict[str, str]:
        exchange_type = str(payload.get('type') or '').strip().lower()
        api_key = str(payload.get('api_key') or '').strip()
        api_secret = str(payload.get('api_secret') or '').strip()
        password = str(payload.get('password') or '').strip()
        if exchange_type not in SUPPORTED_EXCHANGE_TYPES:
            raise ValidationError('当前用户尚未配置有效的交易所类型')
        if not api_key:
            raise ValidationError('当前用户尚未配置 API Key')
        if not api_secret:
            raise ValidationError('当前用户尚未配置 API Secret')
        if exchange_type == 'okx' and not password:
            raise ValidationError('当前用户尚未配置 OKX Password')
        return {
            'type': exchange_type,
            'api_key': api_key,
            'api_secret': api_secret,
            'password': password,
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
