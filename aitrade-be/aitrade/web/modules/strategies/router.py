from __future__ import annotations

import json
from datetime import datetime, timezone

from ...api_response import success_response
from ...dependencies import get_config
from ...dependencies import get_current_user
from ...exceptions import NotFoundError
from ...exceptions import ValidationError
from ....config.config_file import Config
from ....db import Base
from ....db import StrategyProfileModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ....trade.strategies.registry import get_strategy_definition
from ....trade.strategies.registry import list_strategy_definitions
from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from .params import normalize_strategy_params

router = APIRouter()


class StrategySaveRequest(BaseModel):
    id: int | None = None
    strategyType: str
    name: str
    description: str = ''
    enabled: bool = True
    params: dict


class StrategyDeleteRequest(BaseModel):
    id: int


def _ensure_default_profiles(database_url: str):
    engine = get_engine(database_url)
    session_factory = get_session_factory(database_url)
    Base.metadata.create_all(engine)
    definitions = list_strategy_definitions()
    with session_factory() as session:
        for item in definitions:
            exists = session.query(StrategyProfileModel).filter(StrategyProfileModel.strategy_type == item['strategyType']).first()
            if exists is not None:
                continue
            now = datetime.now(timezone.utc).isoformat()
            session.add(
                StrategyProfileModel(
                    strategy_type=item['strategyType'],
                    name=item['displayName'],
                    description=item['description'],
                    enabled=item['strategyType'] == 'gpt',
                    params_json=json.dumps(item['defaultParams'], ensure_ascii=False),
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
    _: dict = Depends(get_current_user),
):
    _ensure_default_profiles(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    definitions = {item['strategyType']: item for item in list_strategy_definitions()}
    with session_factory() as session:
        models = session.query(StrategyProfileModel).order_by(StrategyProfileModel.id.asc()).all()
        rows = [
            {
                'id': model.id,
                'strategyType': model.strategy_type,
                'name': model.name,
                'description': model.description,
                'enabled': bool(model.enabled),
                'params': json.loads(model.params_json),
                'schemaVersion': model.schema_version,
                'createdAt': model.created_at,
                'updatedAt': model.updated_at,
                'definition': definitions.get(model.strategy_type),
            }
            for model in models
        ]
    return success_response(rows)


@router.post('/save')
def save_strategy(
    payload: StrategySaveRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    if not payload.name.strip():
        raise ValidationError('策略配置名称不能为空')
    definition = get_strategy_definition(payload.strategyType)
    normalized_params = normalize_strategy_params(definition, payload.params)
    _ensure_default_profiles(config.trade_persistence_config['database_url'])
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    now = datetime.now(timezone.utc).isoformat()
    with session_factory() as session:
        if payload.id is None:
            model = StrategyProfileModel(
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
            model.strategy_type = payload.strategyType
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
        'strategyType': model.strategy_type,
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
def delete_strategy(
    payload: StrategyDeleteRequest,
    config: Config = Depends(get_config),
    _: dict = Depends(get_current_user),
):
    session_factory = get_session_factory(config.trade_persistence_config['database_url'])
    with session_factory() as session:
        model = session.get(StrategyProfileModel, payload.id)
        if model is None:
            raise NotFoundError('策略配置不存在')
        session.delete(model)
        session.commit()
    return success_response({'deleted': True, 'id': payload.id})
