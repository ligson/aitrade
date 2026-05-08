from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect
from sqlalchemy import text

from ...api_response import success_response
from ...dependencies import apply_owner_scope
from ...dependencies import ensure_owner_access
from ...dependencies import get_config
from ...dependencies import get_current_user
from ...dependencies import get_primary_admin_user_id
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ....config.config_file import Config
from ....db import Base
from ....db import StrategyProfileModel
from ....db import TradeTaskProfileModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.strategies.fusion_profile import summarize_fusion_strategy_profile_config
from ....trade.strategies.registry import get_strategy_definition
from ....trade.strategies.registry import list_strategy_definitions
from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from .params import normalize_strategy_params

router = APIRouter()
logger = logging.getLogger(__name__)


class StrategySaveRequest(BaseModel):
    id: int | None = None
    strategyType: str
    name: str
    description: str = ''
    enabled: bool = True
    params: dict


class StrategyDeleteRequest(BaseModel):
    id: int


class InvalidStrategyProfileItem(BaseModel):
    id: int
    strategyType: str
    name: str
    enabled: bool
    createdAt: str
    updatedAt: str
    errorStage: str
    errorMessage: str


def _serialize_strategy_profile(
    model: StrategyProfileModel,
    definition: dict[str, Any] | None,
    normalized_params: dict[str, Any],
    fusion_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        'id': model.id,
        'ownerUserId': model.owner_user_id,
        'strategyType': model.strategy_type,
        'name': model.name,
        'description': model.description,
        'enabled': bool(model.enabled),
        'params': normalized_params,
        'schemaVersion': model.schema_version,
        'createdAt': model.created_at,
        'updatedAt': model.updated_at,
        'definition': definition,
        'fusionSummary': fusion_summary,
    }


def _serialize_invalid_strategy_profile(
    model: StrategyProfileModel,
    error_stage: str,
    error_message: str,
) -> dict[str, Any]:
    return InvalidStrategyProfileItem(
        id=model.id,
        strategyType=model.strategy_type,
        name=model.name,
        enabled=bool(model.enabled),
        createdAt=model.created_at,
        updatedAt=model.updated_at,
        errorStage=error_stage,
        errorMessage=error_message,
    ).model_dump()


def _list_task_profile_references(session, strategy_profile_id: int) -> list[TradeTaskProfileModel]:
    return (
        session.query(TradeTaskProfileModel)
        .filter(TradeTaskProfileModel.strategy_profile_id == strategy_profile_id)
        .order_by(TradeTaskProfileModel.id.asc())
        .all()
    )


def _list_fusion_strategy_references(session, strategy_profile_id: int) -> list[StrategyProfileModel]:
    fusion_models = (
        session.query(StrategyProfileModel)
        .filter(StrategyProfileModel.strategy_type == 'spot_multi_signal_fusion')
        .filter(StrategyProfileModel.id != strategy_profile_id)
        .order_by(StrategyProfileModel.id.asc())
        .all()
    )
    referenced_models: list[StrategyProfileModel] = []
    for model in fusion_models:
        try:
            params = json.loads(model.params_json or '{}')
        except Exception as exc:
            logger.warning('解析融合策略配置失败，跳过引用检查: strategy_profile_id=%s error=%s', model.id, exc)
            continue
        kline_nodes = params.get('klineNodes')
        if not isinstance(kline_nodes, list):
            continue
        for item in kline_nodes:
            if not isinstance(item, dict):
                continue
            if item.get('strategyProfileId') == strategy_profile_id:
                referenced_models.append(model)
                break
    return referenced_models


def _build_delete_block_reason(session, strategy_profile_id: int) -> str | None:
    task_profile_refs = _list_task_profile_references(session, strategy_profile_id)
    fusion_refs = _list_fusion_strategy_references(session, strategy_profile_id)
    reason_lines: list[str] = []
    if task_profile_refs:
        task_labels = '、'.join(f"#{item.id} {item.name}" for item in task_profile_refs)
        reason_lines.append(f'交易任务配置正在引用该策略：{task_labels}')
    if fusion_refs:
        fusion_labels = '、'.join(f"#{item.id} {item.name}" for item in fusion_refs)
        reason_lines.append(f'融合策略节点正在引用该策略：{fusion_labels}')
    if not reason_lines:
        return None
    return '当前策略配置仍被引用，请先处理相关配置后再删除：' + '；'.join(reason_lines)


def _ensure_strategy_profile_schema(database_url: str) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    if 'strategy_profiles' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('strategy_profiles')}
    fallback_owner_user_id = get_primary_admin_user_id(database_url)
    with engine.begin() as connection:
        if 'owner_user_id' not in columns:
            logging.info('检测到 strategy_profiles 缺少 owner_user_id，自动补列')
            connection.execute(text('ALTER TABLE strategy_profiles ADD COLUMN owner_user_id INTEGER'))
        connection.execute(
            text('UPDATE strategy_profiles SET owner_user_id = :owner_user_id WHERE owner_user_id IS NULL'),
            {'owner_user_id': fallback_owner_user_id},
        )
        connection.execute(text('CREATE INDEX IF NOT EXISTS idx_strategy_profiles_owner_created_at ON strategy_profiles (owner_user_id, created_at)'))



def _ensure_default_profiles(database_url: str, owner_user_id: int):
    _ensure_strategy_profile_schema(database_url)
    engine = get_engine(database_url)
    session_factory = get_session_factory(database_url)
    Base.metadata.create_all(engine)
    definitions = list_strategy_definitions()
    with session_factory() as session:
        for item in definitions:
            exists = session.query(StrategyProfileModel).filter(
                StrategyProfileModel.owner_user_id == owner_user_id,
                StrategyProfileModel.strategy_type == item['strategyType'],
            ).first()
            if exists is not None:
                continue
            try:
                default_params = normalize_strategy_params(item, item['defaultParams'])
            except Exception as exc:
                logger.warning('跳过自动补种默认策略配置：owner_user_id=%s strategy_type=%s error=%s', owner_user_id, item['strategyType'], exc)
                continue
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                StrategyProfileModel(
                    owner_user_id=owner_user_id,
                    strategy_type=item['strategyType'],
                    name=item['displayName'],
                    description=item['description'],
                    enabled=item['strategyType'] == 'gpt',
                    params_json=json.dumps(default_params, ensure_ascii=False),
                    schema_version=item['schemaVersion'],
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()


@router.post('/definitions')
def strategy_definitions(_: dict = Depends(get_current_user)):
    return success_response(list_strategy_definitions())


@router.post('/list')
def strategy_profiles(
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = int(current_user.get('id') or 0)
    if owner_user_id <= 0:
        raise ValidationError('当前用户信息无效')
    _ensure_default_profiles(config.trade_persistence_config['database_url'], owner_user_id)
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    definitions = {item['strategyType']: item for item in list_strategy_definitions()}
    with session_factory() as session:
        models = apply_owner_scope(session.query(StrategyProfileModel), StrategyProfileModel, current_user).order_by(StrategyProfileModel.id.asc()).all()
        rows: list[dict[str, Any]] = []
        invalid_rows: list[dict[str, Any]] = []
        for model in models:
            definition = definitions.get(model.strategy_type)
            try:
                raw_params = json.loads(model.params_json or '{}')
            except Exception as exc:
                logger.warning('策略配置 JSON 解析失败，已跳过该条记录: strategy_profile_id=%s error=%s', model.id, exc)
                invalid_rows.append(_serialize_invalid_strategy_profile(model, 'json_load', f'策略配置 JSON 解析失败: {exc}'))
                continue
            try:
                normalized_params = normalize_strategy_params(definition, raw_params) if definition is not None else raw_params
            except Exception as exc:
                logger.warning('策略配置归一化失败，已跳过该条记录: strategy_profile_id=%s strategy_type=%s error=%s', model.id, model.strategy_type, exc)
                invalid_rows.append(_serialize_invalid_strategy_profile(model, 'normalize', str(exc)))
                continue
            try:
                fusion_summary = summarize_fusion_strategy_profile_config(normalized_params) if model.strategy_type == 'spot_multi_signal_fusion' else None
            except Exception as exc:
                logger.warning('策略配置摘要生成失败，已跳过该条记录: strategy_profile_id=%s strategy_type=%s error=%s', model.id, model.strategy_type, exc)
                invalid_rows.append(_serialize_invalid_strategy_profile(model, 'summarize', str(exc)))
                continue
            rows.append(_serialize_strategy_profile(model, definition, normalized_params, fusion_summary))
    return success_response({
        'items': rows,
        'invalidItems': invalid_rows,
        'summary': {
            'total': len(rows) + len(invalid_rows),
            'validCount': len(rows),
            'invalidCount': len(invalid_rows),
        },
    })


@router.post('/save')
def save_strategy(
    payload: StrategySaveRequest,
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    if not payload.name.strip():
        raise ValidationError('策略配置名称不能为空')
    owner_user_id = int(current_user.get('id') or 0)
    if owner_user_id <= 0:
        raise ValidationError('当前用户信息无效')
    definition = get_strategy_definition(payload.strategyType)
    normalized_params = normalize_strategy_params(definition, payload.params)
    _ensure_default_profiles(config.trade_persistence_config['database_url'], owner_user_id)
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    now = datetime.now(timezone.utc).isoformat()
    with session_factory() as session:
        if payload.id is None:
            model = StrategyProfileModel(
                owner_user_id=owner_user_id,
                strategy_type=payload.strategyType,
                name=payload.name.strip(),
                description=payload.description.strip(),
                enabled=payload.enabled,
                params_json=json.dumps(normalized_params, ensure_ascii=False),
                schema_version=definition['schemaVersion'],
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.commit()
            session.refresh(model)
        else:
            model = session.get(StrategyProfileModel, payload.id)
            if model is None:
                raise NotFoundError('策略配置不存在')
            ensure_owner_access(current_user, model.owner_user_id)
            model.strategy_type = payload.strategyType
            model.name = payload.name.strip()
            model.description = payload.description.strip()
            model.enabled = payload.enabled
            model.params_json = json.dumps(normalized_params, ensure_ascii=False)
            model.schema_version = definition['schemaVersion']
            model.updated_at = now
            session.commit()
            session.refresh(model)
    saved_params = json.loads(model.params_json)
    return success_response({
        'id': model.id,
        'ownerUserId': model.owner_user_id,
        'strategyType': model.strategy_type,
        'name': model.name,
        'description': model.description,
        'enabled': bool(model.enabled),
        'params': saved_params,
        'schemaVersion': model.schema_version,
        'createdAt': model.created_at,
        'updatedAt': model.updated_at,
        'definition': definition,
        'fusionSummary': summarize_fusion_strategy_profile_config(saved_params) if model.strategy_type == 'spot_multi_signal_fusion' else None,
    })


@router.post('/delete')
def delete_strategy(
    payload: StrategyDeleteRequest,
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    _ensure_strategy_profile_schema(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    with session_factory() as session:
        model = session.get(StrategyProfileModel, payload.id)
        if model is None:
            raise NotFoundError('策略配置不存在')
        ensure_owner_access(current_user, model.owner_user_id)
        delete_block_reason = _build_delete_block_reason(session, payload.id)
        if delete_block_reason:
            logger.warning('拒绝删除仍被引用的策略配置: strategy_profile_id=%s strategy_type=%s', model.id, model.strategy_type)
            raise ValidationError(delete_block_reason)
        session.delete(model)
        session.commit()
    return success_response({'deleted': True, 'id': payload.id})
