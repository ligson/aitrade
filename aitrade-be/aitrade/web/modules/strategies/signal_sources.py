from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter
from fastapi import Depends

from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import get_current_user
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ....config.config_file import Config
from ....db import Base
from ....db import SignalSourceProfileModel
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



def _ensure_default_profiles(database_url: str):
    engine = get_engine(database_url)
    session_factory = get_session_factory(database_url)
    Base.metadata.create_all(engine)
    definitions = list_signal_source_definitions()
    with session_factory() as session:
        for item in definitions:
            exists = session.query(SignalSourceProfileModel).filter(SignalSourceProfileModel.source_type == item['sourceType']).first()
            if exists is not None:
                continue
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                SignalSourceProfileModel(
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
    _: dict = Depends(get_current_user),
):
    _ensure_default_profiles(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    definitions = {item['sourceType']: item for item in list_signal_source_definitions()}
    with session_factory() as session:
        models = session.query(SignalSourceProfileModel).order_by(SignalSourceProfileModel.id.asc()).all()
        rows = []
        for model in models:
            definition = definitions.get(model.source_type)
            raw_params = json.loads(model.params_json or '{}')
            normalized_params = normalize_signal_source_params(definition, raw_params) if definition is not None else raw_params
            rows.append({
                'id': model.id,
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
    _: dict = Depends(get_current_user),
):
    if not payload.name.strip():
        raise ValidationError('信号源名称不能为空')
    definition = get_signal_source_definition(payload.sourceType)
    normalized_params = normalize_signal_source_params(definition, payload.params)
    _ensure_default_profiles(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    now = datetime.now(timezone.utc).isoformat()
    with session_factory() as session:
        if payload.id is None:
            model = SignalSourceProfileModel(
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
    _: dict = Depends(get_current_user),
):
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    with session_factory() as session:
        model = session.get(SignalSourceProfileModel, payload.id)
        if model is None:
            raise NotFoundError('信号源配置不存在')
        session.delete(model)
        session.commit()
    return success_response({'deleted': True, 'id': payload.id})
