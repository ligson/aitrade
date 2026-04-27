from __future__ import annotations

import copy
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....config.config_file import Config
from ....config.config_file import ConfigValidationError
from ....config.log_config import resolve_log_dir
from ....db import Base
from ....db import SystemSettingProfileModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import ValidationError

SYSTEM_SETTING_SCHEMA_VERSION = 1
SYSTEM_SETTING_PROFILE_NAME = '默认系统设置'
SYSTEM_SETTING_PROFILE_DESCRIPTION = '由 Web 管理台维护的非敏感系统配置'
SUPPORTED_GPT_PROVIDERS = {'deepseek', 'openai'}
SUPPORTED_BACKTEST_DATA_FORMATS = {'json', 'jsongz'}
SUPPORTED_BACKTEST_ARCHIVE_FORMATS = {'zip'}


class SystemService:
    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        self.log_dir = Path(resolve_log_dir()).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def get_settings(self) -> dict[str, Any]:
        effective_config, profile = self.get_effective_config()
        backtest_config = effective_config.backtest_config
        base_backtest_config = self.config.backtest_config
        backtest_data_dir = Path(base_backtest_config['data_dir']).expanduser().resolve()
        freqtrade_user_data_dir = Path(base_backtest_config['user_data_dir']).expanduser().resolve()
        return {
            'readonly': {
                'backtestDataDir': str(backtest_data_dir),
                'freqtradeUserDataDir': str(freqtrade_user_data_dir),
                'appLogDir': str(self.log_dir),
            },
            'editable': self._serialize_editable_settings(effective_config),
            'meta': {
                'id': profile.id,
                'name': profile.name,
                'description': profile.description,
                'schemaVersion': profile.schema_version,
                'updatedAt': profile.updated_at,
            },
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        editable = payload.get('editable')
        if not isinstance(editable, dict):
            raise ValidationError('系统设置内容不能为空')
        normalized = self._normalize_editable_settings(editable)
        _, profile = self._ensure_default_profile()
        now = self._now_iso()
        with self.Session() as session:
            model = session.get(SystemSettingProfileModel, profile.id)
            if model is None:
                raise ValidationError('系统设置记录不存在')
            model.name = str(payload.get('name') or model.name or SYSTEM_SETTING_PROFILE_NAME).strip() or SYSTEM_SETTING_PROFILE_NAME
            description = payload.get('description')
            if description is None:
                description = model.description
            model.description = str(description or '').strip()
            model.enabled = True
            model.params_json = json.dumps(normalized, ensure_ascii=False)
            model.schema_version = SYSTEM_SETTING_SCHEMA_VERSION
            model.updated_at = now
            session.commit()
        return self.get_settings()

    def get_effective_config(self) -> tuple[Config, SystemSettingProfileModel]:
        override_params, profile = self._ensure_default_profile()
        config_data = self.build_effective_config_dict(override_params)
        try:
            return Config.from_dict(config_data, mode='web'), profile
        except ConfigValidationError as exc:
            raise ValidationError(str(exc)) from exc

    def build_effective_config_dict(self, override_params: dict[str, Any] | None = None) -> dict[str, Any]:
        if override_params is None:
            override_params, _ = self._ensure_default_profile()
        config_data = copy.deepcopy(self.config.config)
        app_cfg = dict(config_data.get('app') or {})

        gpt_cfg = dict(app_cfg.get('gpt') or {})
        gpt_override = dict(override_params.get('gpt') or {})
        if 'provider' in gpt_override:
            gpt_cfg['provider'] = gpt_override['provider']
        if 'model' in gpt_override:
            gpt_cfg['model'] = gpt_override['model']
        app_cfg['gpt'] = gpt_cfg

        trade_cfg = dict(app_cfg.get('trade') or {})
        persistence_cfg = dict(trade_cfg.get('persistence') or {})
        trade_override = dict(override_params.get('trade') or {})
        persistence_override = dict(trade_override.get('persistence') or {})
        if 'persist_position' in persistence_override:
            persistence_cfg['persist_position'] = persistence_override['persist_position']
        if 'restore_position_on_startup' in persistence_override:
            persistence_cfg['restore_position_on_startup'] = persistence_override['restore_position_on_startup']
        trade_cfg['persistence'] = persistence_cfg
        app_cfg['trade'] = trade_cfg

        backtest_cfg = dict(app_cfg.get('backtest') or {})
        backtest_override = dict(override_params.get('backtest') or {})
        for key in (
            'supported_symbols',
            'supported_timeframes',
            'default_symbol',
            'default_timeframe',
            'download_timerange',
            'data_format_ohlcv',
            'export_archive_format',
        ):
            if key in backtest_override:
                backtest_cfg[key] = backtest_override[key]
        app_cfg['backtest'] = backtest_cfg

        config_data['app'] = app_cfg
        return config_data

    def list_log_files(self, offset: int, size: int, keyword: str = '', log_type: str = '') -> tuple[int, list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.log_dir.glob('*.log'), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            item = self._serialize_log_file(path)
            if keyword.strip() and keyword.strip().lower() not in item['filename'].lower():
                continue
            if log_type.strip() and item['type'] != log_type.strip():
                continue
            rows.append(item)
        total = len(rows)
        return total, rows[offset: offset + size]

    def read_log_content(self, filename: str, tail_lines: int = 200) -> dict[str, Any]:
        if tail_lines <= 0:
            raise ValidationError('tailLines 必须大于 0')
        if tail_lines > 2000:
            raise ValidationError('tailLines 不能超过 2000')
        path = self._resolve_log_file(filename)
        with path.open('r', encoding='utf-8', errors='replace') as file:
            lines = deque(file, maxlen=tail_lines)
        content = ''.join(lines)
        return {
            **self._serialize_log_file(path),
            'tailLines': tail_lines,
            'content': content,
            'truncated': path.stat().st_size > len(content.encode('utf-8')) if content else False,
        }

    def _ensure_default_profile(self) -> tuple[dict[str, Any], SystemSettingProfileModel]:
        with self.Session() as session:
            profile = (
                session.query(SystemSettingProfileModel)
                .filter(SystemSettingProfileModel.enabled.is_(True))
                .order_by(SystemSettingProfileModel.id.asc())
                .first()
            )
            if profile is None:
                profile = session.query(SystemSettingProfileModel).order_by(SystemSettingProfileModel.id.asc()).first()
            if profile is None:
                now = self._now_iso()
                profile = SystemSettingProfileModel(
                    name=SYSTEM_SETTING_PROFILE_NAME,
                    description=SYSTEM_SETTING_PROFILE_DESCRIPTION,
                    enabled=True,
                    params_json=json.dumps(self._build_default_params(), ensure_ascii=False),
                    schema_version=SYSTEM_SETTING_SCHEMA_VERSION,
                    created_at=now,
                    updated_at=now,
                )
                session.add(profile)
                session.commit()
                session.refresh(profile)
            else:
                if not profile.enabled:
                    profile.enabled = True
                    session.commit()
                    session.refresh(profile)
            params = self._normalize_params_json(profile.params_json)
            normalized = self._normalize_editable_settings(self._serialize_editable_payload(params))
            normalized_json = json.dumps(normalized, ensure_ascii=False)
            if profile.params_json != normalized_json or profile.schema_version != SYSTEM_SETTING_SCHEMA_VERSION:
                profile.params_json = normalized_json
                profile.schema_version = SYSTEM_SETTING_SCHEMA_VERSION
                session.commit()
                session.refresh(profile)
            return normalized, profile

    def _build_default_params(self) -> dict[str, Any]:
        return self._normalize_editable_settings(
            {
                'gptProvider': self.config.gpt_provider,
                'gptModel': self.config.gpt_model,
                'persistPosition': self.config.trade_persistence_config['persist_position'],
                'restorePositionOnStartup': self.config.trade_persistence_config['restore_position_on_startup'],
                'supportedSymbols': list(self.config.backtest_config['supported_symbols']),
                'supportedTimeframes': list(self.config.backtest_config['supported_timeframes']),
                'defaultSymbol': self.config.backtest_config['default_symbol'],
                'defaultTimeframe': self.config.backtest_config['default_timeframe'],
                'downloadTimerange': self.config.backtest_config['download_timerange'],
                'dataFormatOhlcv': self.config.backtest_config['data_format_ohlcv'],
                'exportArchiveFormat': self.config.backtest_config['export_archive_format'],
            }
        )

    def _serialize_editable_settings(self, config: Config) -> dict[str, Any]:
        return {
            'gptProvider': config.gpt_provider,
            'gptModel': config.gpt_model,
            'persistPosition': bool(config.trade_persistence_config['persist_position']),
            'restorePositionOnStartup': bool(config.trade_persistence_config['restore_position_on_startup']),
            'supportedSymbols': list(config.backtest_config['supported_symbols']),
            'supportedTimeframes': list(config.backtest_config['supported_timeframes']),
            'defaultSymbol': config.backtest_config['default_symbol'],
            'defaultTimeframe': config.backtest_config['default_timeframe'],
            'downloadTimerange': config.backtest_config['download_timerange'],
            'dataFormatOhlcv': config.backtest_config['data_format_ohlcv'],
            'exportArchiveFormat': config.backtest_config['export_archive_format'],
        }

    def _serialize_editable_payload(self, params: dict[str, Any]) -> dict[str, Any]:
        gpt_params = dict(params.get('gpt') or {})
        trade_params = dict(params.get('trade') or {})
        persistence_params = dict(trade_params.get('persistence') or {})
        backtest_params = dict(params.get('backtest') or {})
        return {
            'gptProvider': gpt_params.get('provider', self.config.gpt_provider),
            'gptModel': gpt_params.get('model', self.config.gpt_model),
            'persistPosition': persistence_params.get('persist_position', self.config.trade_persistence_config['persist_position']),
            'restorePositionOnStartup': persistence_params.get(
                'restore_position_on_startup',
                self.config.trade_persistence_config['restore_position_on_startup'],
            ),
            'supportedSymbols': backtest_params.get('supported_symbols', self.config.backtest_config['supported_symbols']),
            'supportedTimeframes': backtest_params.get('supported_timeframes', self.config.backtest_config['supported_timeframes']),
            'defaultSymbol': backtest_params.get('default_symbol', self.config.backtest_config['default_symbol']),
            'defaultTimeframe': backtest_params.get('default_timeframe', self.config.backtest_config['default_timeframe']),
            'downloadTimerange': backtest_params.get('download_timerange', self.config.backtest_config['download_timerange']),
            'dataFormatOhlcv': backtest_params.get('data_format_ohlcv', self.config.backtest_config['data_format_ohlcv']),
            'exportArchiveFormat': backtest_params.get('export_archive_format', self.config.backtest_config['export_archive_format']),
        }

    def _normalize_editable_settings(self, editable: dict[str, Any]) -> dict[str, Any]:
        provider = str(editable.get('gptProvider') or '').strip()
        if provider not in SUPPORTED_GPT_PROVIDERS:
            raise ValidationError('GPT 提供方仅支持 deepseek 或 openai')
        model = str(editable.get('gptModel') or '').strip()
        if not model:
            raise ValidationError('GPT 模型名称不能为空')
        persist_position = editable.get('persistPosition')
        if not isinstance(persist_position, bool):
            raise ValidationError('是否持久化当前持仓必须是布尔值')
        restore_position_on_startup = editable.get('restorePositionOnStartup')
        if not isinstance(restore_position_on_startup, bool):
            raise ValidationError('是否在启动时恢复持仓必须是布尔值')
        supported_symbols = self._normalize_string_list(editable.get('supportedSymbols'), '支持交易对')
        supported_timeframes = self._normalize_string_list(editable.get('supportedTimeframes'), '支持周期')
        default_symbol = str(editable.get('defaultSymbol') or '').strip()
        if not default_symbol:
            raise ValidationError('默认交易对不能为空')
        if default_symbol not in supported_symbols:
            raise ValidationError('默认交易对必须包含在支持交易对列表中')
        default_timeframe = str(editable.get('defaultTimeframe') or '').strip()
        if not default_timeframe:
            raise ValidationError('默认周期不能为空')
        if default_timeframe not in supported_timeframes:
            raise ValidationError('默认周期必须包含在支持周期列表中')
        download_timerange = str(editable.get('downloadTimerange') or '').strip()
        if not download_timerange:
            raise ValidationError('下载时间范围不能为空')
        data_format_ohlcv = str(editable.get('dataFormatOhlcv') or '').strip()
        if data_format_ohlcv not in SUPPORTED_BACKTEST_DATA_FORMATS:
            raise ValidationError('历史数据格式仅支持 json 或 jsongz')
        export_archive_format = str(editable.get('exportArchiveFormat') or '').strip()
        if export_archive_format not in SUPPORTED_BACKTEST_ARCHIVE_FORMATS:
            raise ValidationError('导出压缩格式当前仅支持 zip')
        return {
            'gpt': {
                'provider': provider,
                'model': model,
            },
            'trade': {
                'persistence': {
                    'persist_position': persist_position,
                    'restore_position_on_startup': restore_position_on_startup,
                }
            },
            'backtest': {
                'supported_symbols': supported_symbols,
                'supported_timeframes': supported_timeframes,
                'default_symbol': default_symbol,
                'default_timeframe': default_timeframe,
                'download_timerange': download_timerange,
                'data_format_ohlcv': data_format_ohlcv,
                'export_archive_format': export_archive_format,
            },
        }

    @staticmethod
    def _normalize_string_list(value: Any, label: str) -> list[str]:
        if not isinstance(value, list):
            raise ValidationError(f'{label}必须是字符串数组')
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or '').strip()
            if not text:
                continue
            if text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        if not normalized:
            raise ValidationError(f'{label}不能为空')
        return normalized

    @staticmethod
    def _normalize_params_json(value: str) -> dict[str, Any]:
        try:
            payload = json.loads(value or '{}')
        except json.JSONDecodeError as exc:
            raise ValidationError('系统设置存储内容损坏，无法解析') from exc
        if not isinstance(payload, dict):
            raise ValidationError('系统设置存储内容格式非法')
        return payload

    def _serialize_log_file(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            'filename': path.name,
            'path': str(path),
            'type': 'trade' if path.name.startswith('trade_') else 'app',
            'size': stat.st_size,
            'modifiedAt': stat.st_mtime,
        }

    def _resolve_log_file(self, filename: str) -> Path:
        normalized = str(filename or '').strip()
        if not normalized:
            raise ValidationError('日志文件名不能为空')
        path = (self.log_dir / normalized).resolve()
        if path.parent != self.log_dir:
            raise ValidationError('日志文件路径非法')
        if not path.exists() or not path.is_file():
            raise ValidationError(f'未找到日志文件：{normalized}')
        if path.suffix.lower() != '.log':
            raise ValidationError('当前仅支持查看 .log 日志文件')
        return path

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
