from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy import text
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi import Depends

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
from ....db import SignalSourceProfileModel
from ....db import StrategyProfileModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.strategies.signal_source_registry import get_signal_source_definition
from ....trade.strategies.signal_source_registry import list_signal_source_definitions

router = APIRouter()


class SignalSourceSaveRequest(BaseModel):
    id: int | None = None
    sourceType: str
    name: str
    description: str = ''
    enabled: bool = True
    params: dict


class SignalSourceDeleteRequest(BaseModel):
    id: int



def _validate_signal_source_field(field_name: str, schema: dict, value):
    field_type = schema.get('type')
    if field_type == 'boolean':
        if not isinstance(value, bool):
            raise ValidationError(f'信号源参数 {field_name} 必须是布尔值')
    elif field_type == 'integer':
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f'信号源参数 {field_name} 必须是整数')
    elif field_type == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f'信号源参数 {field_name} 必须是数字')
    elif field_type == 'string':
        if value is not None and not isinstance(value, str):
            raise ValidationError(f'信号源参数 {field_name} 必须是字符串')
    else:
        raise ValidationError(f'不支持的信号源参数类型：{field_type}')



def normalize_signal_source_params(definition: dict, params: dict) -> dict:
    if not isinstance(params, dict):
        raise ValidationError('信号源参数必须是对象')
    normalized = dict(definition['defaultParams'])
    normalized.update(params)
    schema_by_field = {item['field']: item for item in definition['paramSchema']}
    extra_fields = sorted(set(normalized.keys()) - set(schema_by_field.keys()))
    if extra_fields:
        raise ValidationError(f"存在未定义的信号源参数：{', '.join(extra_fields)}")
    for field_name, schema in schema_by_field.items():
        value = normalized.get(field_name)
        if schema.get('required') and (value is None or value == ''):
            raise ValidationError(f'缺少必填信号源参数：{field_name}')
        _validate_signal_source_field(field_name, schema, value)
        if value is None or value == '':
            continue
        if 'min' in schema and value < schema['min']:
            raise ValidationError(f"信号源参数 {field_name} 不能小于 {schema['min']}")
        if 'max' in schema and value > schema['max']:
            raise ValidationError(f"信号源参数 {field_name} 不能大于 {schema['max']}")
    return normalized



def _find_fusion_strategy_references(session, signal_source_profile_id: int) -> list[StrategyProfileModel]:
    fusion_models = (
        session.query(StrategyProfileModel)
        .filter(StrategyProfileModel.strategy_type == 'spot_multi_signal_fusion')
        .order_by(StrategyProfileModel.id.asc())
        .all()
    )
    referenced_models: list[StrategyProfileModel] = []
    for model in fusion_models:
        try:
            params = json.loads(model.params_json or '{}')
        except Exception:
            continue
        nodes = params.get('signalSourceNodes')
        if not isinstance(nodes, list):
            continue
        for item in nodes:
            if not isinstance(item, dict):
                continue
            if item.get('signalSourceProfileId') == signal_source_profile_id:
                referenced_models.append(model)
                break
    return referenced_models



def _build_delete_block_reason(session, signal_source_profile_id: int) -> str | None:
    fusion_refs = _find_fusion_strategy_references(session, signal_source_profile_id)
    if not fusion_refs:
        return None
    fusion_labels = '、'.join(f"#{item.id} {item.name}" for item in fusion_refs)
    return f'当前信号源配置仍被融合策略引用，请先处理相关配置后再删除：{fusion_labels}'



def _ensure_signal_source_profile_schema(database_url: str) -> None:
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    if 'signal_source_profiles' not in inspector.get_table_names():
        return
    columns = {column['name'] for column in inspector.get_columns('signal_source_profiles')}
    fallback_owner_user_id = get_primary_admin_user_id(database_url)
    with engine.begin() as connection:
        if 'owner_user_id' not in columns:
            connection.execute(text('ALTER TABLE signal_source_profiles ADD COLUMN owner_user_id INTEGER'))
        connection.execute(
            text('UPDATE signal_source_profiles SET owner_user_id = :owner_user_id WHERE owner_user_id IS NULL'),
            {'owner_user_id': fallback_owner_user_id},
        )
        connection.execute(text('CREATE INDEX IF NOT EXISTS idx_signal_source_profiles_owner_created_at ON signal_source_profiles (owner_user_id, created_at)'))



def _ensure_default_profiles(database_url: str, owner_user_id: int):
    _ensure_signal_source_profile_schema(database_url)
    engine = get_engine(database_url)
    session_factory = get_session_factory(database_url)
    Base.metadata.create_all(engine)
    definitions = list_signal_source_definitions()
    with session_factory() as session:
        for item in definitions:
            exists = session.query(SignalSourceProfileModel).filter(
                SignalSourceProfileModel.owner_user_id == owner_user_id,
                SignalSourceProfileModel.source_type == item['sourceType'],
            ).first()
            if exists is not None:
                continue
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                SignalSourceProfileModel(
                    owner_user_id=owner_user_id,
                    source_type=item['sourceType'],
                    name=item['displayName'],
                    description=item['description'],
                    enabled=item['sourceType'] == 'trade_flow',
                    params_json=json.dumps(item['defaultParams'], ensure_ascii=False),
                    schema_version=item['schemaVersion'],
                    created_at=now,
                    updated_at=now,
                )
            )
        session.commit()


@router.post('/definitions')
def signal_source_definitions(_: dict = Depends(get_current_user)):
    return success_response(list_signal_source_definitions())


@router.post('/list')
def signal_source_profiles(
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    owner_user_id = int(current_user.get('id') or 0)
    if owner_user_id <= 0:
        raise ValidationError('当前用户信息无效')
    _ensure_default_profiles(config.trade_persistence_config['database_url'], owner_user_id)
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    definitions = {item['sourceType']: item for item in list_signal_source_definitions()}
    with session_factory() as session:
        models = apply_owner_scope(session.query(SignalSourceProfileModel), SignalSourceProfileModel, current_user).order_by(SignalSourceProfileModel.id.asc()).all()
        rows = []
        for model in models:
            definition = definitions.get(model.source_type)
            raw_params = json.loads(model.params_json or '{}')
            normalized_params = normalize_signal_source_params(definition, raw_params) if definition is not None else raw_params
            rows.append({
                'id': model.id,
                'ownerUserId': model.owner_user_id,
                'sourceType': model.source_type,
                'name': model.name,
                'description': model.description,
                'enabled': bool(model.enabled),
                'params': normalized_params,
                'schemaVersion': model.schema_version,
                'createdAt': model.created_at,
                'updatedAt': model.updated_at,
                'definition': definition,
            })
    return success_response(rows)


@router.post('/save')
def save_signal_source(
    payload: SignalSourceSaveRequest,
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    if not payload.name.strip():
        raise ValidationError('信号源名称不能为空')
    owner_user_id = int(current_user.get('id') or 0)
    if owner_user_id <= 0:
        raise ValidationError('当前用户信息无效')
    definition = get_signal_source_definition(payload.sourceType)
    normalized_params = normalize_signal_source_params(definition, payload.params)
    _ensure_default_profiles(config.trade_persistence_config['database_url'], owner_user_id)
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    now = datetime.now(timezone.utc).isoformat()
    with session_factory() as session:
        if payload.id is None:
            model = SignalSourceProfileModel(
                owner_user_id=owner_user_id,
                source_type=payload.sourceType,
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
            model = session.get(SignalSourceProfileModel, payload.id)
            if model is None:
                raise NotFoundError('信号源配置不存在')
            ensure_owner_access(current_user, model.owner_user_id)
            model.source_type = payload.sourceType
            model.name = payload.name.strip()
            model.description = payload.description.strip()
            model.enabled = payload.enabled
            model.params_json = json.dumps(normalized_params, ensure_ascii=False)
            model.schema_version = definition['schemaVersion']
            model.updated_at = now
            session.commit()
            session.refresh(model)
    return success_response({
        'id': model.id,
        'ownerUserId': model.owner_user_id,
        'sourceType': model.source_type,
        'name': model.name,
        'description': model.description,
        'enabled': bool(model.enabled),
        'params': json.loads(model.params_json),
        'schemaVersion': model.schema_version,
        'createdAt': model.created_at,
        'updatedAt': model.updated_at,
        'definition': definition,
    })


@router.post('/delete')
def delete_signal_source(
    payload: SignalSourceDeleteRequest,
    config: Config = Depends(get_config),
    current_user: dict = Depends(get_current_user),
):
    _ensure_signal_source_profile_schema(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    with session_factory() as session:
        model = session.get(SignalSourceProfileModel, payload.id)
        if model is None:
            raise NotFoundError('信号源配置不存在')
        ensure_owner_access(current_user, model.owner_user_id)
        delete_block_reason = _build_delete_block_reason(session, payload.id)
        if delete_block_reason:
            raise ValidationError(delete_block_reason)
        session.delete(model)
        session.commit()
    return success_response({'deleted': True, 'id': payload.id})
