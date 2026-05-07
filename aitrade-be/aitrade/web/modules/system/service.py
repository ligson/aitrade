from __future__ import annotations

import copy
import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....config.config_file import Config
from ....config.config_file import ConfigValidationError
from ....db import Base
from ....db import SystemSettingProfileModel
from ....db.session import get_engine
from ....db.session import get_session_factory
from ...exceptions import ValidationError

SYSTEM_SETTING_SCHEMA_VERSION = 1
SYSTEM_SETTING_PROFILE_NAME = '默认系统设置'
SYSTEM_SETTING_PROFILE_DESCRIPTION = '由 Web 管理台维护的系统配置'
SUPPORTED_GPT_PROVIDERS = {'deepseek', 'openai'}
SUPPORTED_BACKTEST_DATA_FORMATS = {'json', 'jsongz'}
SUPPORTED_BACKTEST_ARCHIVE_FORMATS = {'zip'}
GPT_API_KEY_MASK_PLACEHOLDER = '********'


class SystemService:
    """维护 Web 场景下的系统设置默认档案、归一化与生效配置构建。"""

    def __init__(self, config: Config):
        self.config = config
        self.database_url = config.trade_persistence_config['database_url']
        self.engine = get_engine(self.database_url)
        self.Session = get_session_factory(self.database_url)
        self.log_dir = Path(config.log_dir).expanduser().resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    def get_settings(self) -> dict[str, Any]:
        # readonly 仅展示仍由部署期文件维护的根目录、路径类与数据库连接信息；
        # editable 才是允许页面保存并持久化到数据库的业务默认参数。
        effective_config, profile = self.get_effective_config()
        logging.debug('读取系统设置成功: profile_id=%s schema_version=%s', profile.id, profile.schema_version)
        backtest_config = effective_config.backtest_config
        base_backtest_config = self.config.backtest_config
        backtest_data_dir = Path(base_backtest_config['data_dir']).expanduser().resolve()
        freqtrade_user_data_dir = Path(base_backtest_config['user_data_dir']).expanduser().resolve()
        return {
            'readonly': {
                'dataRootDir': self.config.data_root_dir,
                'dataRootMode': self.config.data_root_mode,
                'tradeDatabaseUrl': self.database_url,
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
        # 前端虽然拆成多个设置子页，但保存接口语义仍然是整份 editable 覆盖保存，
        # 因此前端提交时必须带上其他页面当前值，不能只传本页字段。
        editable = payload.get('editable')
        if not isinstance(editable, dict):
            raise ValidationError('系统设置内容不能为空')
        _, profile = self._ensure_default_profile()
        current_params = self._normalize_params_json(profile.params_json)
        normalized = self._normalize_editable_settings(editable, current_params)
        logging.info(
            '保存系统设置: profile_id=%s provider=%s has_api_key=%s persist_position=%s supported_symbols=%s supported_timeframes=%s',
            profile.id,
            normalized['gpt']['provider'],
            bool(normalized['gpt']['api_key']),
            normalized['trade']['persistence']['persist_position'],
            len(normalized['backtest']['supported_symbols']),
            len(normalized['backtest']['supported_timeframes']),
        )
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
        logging.debug('系统设置保存完成: profile_id=%s 覆盖域=%s', profile.id, ['gpt', 'trade.persistence', 'backtest'])
        return self.get_settings()

    def get_effective_config(self) -> tuple[Config, SystemSettingProfileModel]:
        override_params, profile = self._ensure_default_profile()
        config_data = self.build_effective_config_dict(override_params)
        try:
            return Config.from_dict(config_data, mode='web'), profile
        except ConfigValidationError as exc:
            logging.error('构建系统设置生效配置失败: profile_id=%s error=%s', profile.id, exc)
            raise ValidationError(str(exc)) from exc

    def build_effective_config_dict(self, override_params: dict[str, Any] | None = None) -> dict[str, Any]:
        if override_params is None:
            override_params, _ = self._ensure_default_profile()
        config_data = copy.deepcopy(self.config.config)
        app_cfg = dict(config_data.get('app') or {})

        # 系统设置只对白名单字段做覆盖，避免把数据库里无关字段整段合并回 app。
        gpt_cfg = dict(app_cfg.get('gpt') or {})
        gpt_override = dict(override_params.get('gpt') or {})
        if 'provider' in gpt_override:
            gpt_cfg['provider'] = gpt_override['provider']
        if 'model' in gpt_override:
            gpt_cfg['model'] = gpt_override['model']
        if 'api_key' in gpt_override:
            gpt_cfg['api_key'] = gpt_override['api_key']
        if 'base_url' in gpt_override:
            gpt_cfg['base_url'] = gpt_override['base_url']
        app_cfg['gpt'] = gpt_cfg

        trade_cfg = dict(app_cfg.get('trade') or {})
        persistence_cfg = dict(trade_cfg.get('persistence') or {})
        task_defaults_cfg = dict(trade_cfg.get('task_defaults') or {})
        trade_override = dict(override_params.get('trade') or {})
        persistence_override = dict(trade_override.get('persistence') or {})
        task_defaults_override = dict(trade_override.get('task_defaults') or {})
        if 'persist_position' in persistence_override:
            persistence_cfg['persist_position'] = persistence_override['persist_position']
        if 'restore_position_on_startup' in persistence_override:
            persistence_cfg['restore_position_on_startup'] = persistence_override['restore_position_on_startup']
        for key in ('fee_rate', 'slippage_rate', 'daily_loss_stop_enabled', 'daily_loss_stop_threshold'):
            if key in task_defaults_override:
                task_defaults_cfg[key] = task_defaults_override[key]
        market_feeds_cfg = dict(trade_cfg.get('market_feeds') or {})
        market_feeds_override = dict(trade_override.get('market_feeds') or {})
        trade_flow_cfg = dict(market_feeds_cfg.get('trade_flow') or {})
        trade_flow_override = dict(market_feeds_override.get('trade_flow') or {})
        for key in ('enabled', 'freshness_seconds', 'lookback_trades'):
            if key in trade_flow_override:
                trade_flow_cfg[key] = trade_flow_override[key]
        market_feeds_cfg['trade_flow'] = trade_flow_cfg
        trade_cfg['persistence'] = persistence_cfg
        trade_cfg['task_defaults'] = task_defaults_cfg
        trade_cfg['market_feeds'] = market_feeds_cfg
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
        logging.debug('构建系统设置生效配置完成: 覆盖域=%s', ['gpt', 'trade.persistence', 'backtest'])
        return config_data

    def get_runtime_default_snapshots(self) -> dict[str, Any]:
        effective_config, _ = self.get_effective_config()
        return {
            'tradeFlow': {
                'enabled': bool((effective_config.trade_market_feeds_config.get('trade_flow') or {}).get('enabled', True)),
                'freshnessSeconds': int((effective_config.trade_market_feeds_config.get('trade_flow') or {}).get('freshness_seconds', 120)),
                'lookbackTrades': int((effective_config.trade_market_feeds_config.get('trade_flow') or {}).get('lookback_trades', 200)),
            },
            'taskDefaults': {
                'feeRate': float(effective_config.trade_task_defaults_config['fee_rate']),
                'slippageRate': float(effective_config.trade_task_defaults_config['slippage_rate']),
                'dailyLossStopEnabled': bool(effective_config.trade_task_defaults_config['daily_loss_stop_enabled']),
                'dailyLossStopThreshold': float(effective_config.trade_task_defaults_config['daily_loss_stop_threshold']),
            },
        }

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
        # 系统设置始终保证存在一个启用中的默认档案；
        # 旧档案会在读取时归一化到当前 schema，避免历史字段缺失影响生效配置构建。
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
                logging.info('未找到系统设置档案，自动创建默认档案')
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
                    logging.warning('检测到默认系统设置档案被停用，自动重新启用: profile_id=%s', profile.id)
                    profile.enabled = True
                    session.commit()
                    session.refresh(profile)
            params = self._normalize_params_json(profile.params_json)
            normalized = self._normalize_editable_settings(self._serialize_editable_payload(params), params)
            normalized_json = json.dumps(normalized, ensure_ascii=False)
            if profile.params_json != normalized_json or profile.schema_version != SYSTEM_SETTING_SCHEMA_VERSION:
                logging.warning('系统设置档案内容或 schema 已过期，自动归一化修正: profile_id=%s', profile.id)
                profile.params_json = normalized_json
                profile.schema_version = SYSTEM_SETTING_SCHEMA_VERSION
                profile.updated_at = self._now_iso()
                session.commit()
                session.refresh(profile)
            return normalized, profile

    def _build_default_params(self) -> dict[str, Any]:
        return self._normalize_editable_settings(
            {
                'gptProvider': self.config.gpt_provider,
                'gptModel': self.config.gpt_model,
                'gptApiKey': self.config.gpt_api_key,
                'gptBaseUrl': self.config.gpt_base_url,
                'persistPosition': self.config.trade_persistence_config['persist_position'],
                'restorePositionOnStartup': self.config.trade_persistence_config['restore_position_on_startup'],
                'tradeTaskDefaultFeeRate': self.config.trade_task_defaults_config['fee_rate'],
                'tradeTaskDefaultSlippageRate': self.config.trade_task_defaults_config['slippage_rate'],
                'tradeTaskDefaultDailyLossStopEnabled': self.config.trade_task_defaults_config['daily_loss_stop_enabled'],
                'tradeTaskDefaultDailyLossStopThreshold': self.config.trade_task_defaults_config['daily_loss_stop_threshold'],
                'tradeFlowFeedEnabled': self.config.trade_market_feeds_config['trade_flow']['enabled'],
                'tradeFlowFeedFreshnessSeconds': self.config.trade_market_feeds_config['trade_flow']['freshness_seconds'],
                'tradeFlowFeedLookbackTrades': self.config.trade_market_feeds_config['trade_flow']['lookback_trades'],
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
            'gptApiKey': self._mask_secret(config.gpt_api_key),
            'gptBaseUrl': config.gpt_base_url,
            'hasGptApiKey': bool(config.gpt_api_key),
            'gptApiKeyMasked': self._mask_secret(config.gpt_api_key),
            'persistPosition': bool(config.trade_persistence_config['persist_position']),
            'restorePositionOnStartup': bool(config.trade_persistence_config['restore_position_on_startup']),
            'tradeTaskDefaultFeeRate': float(config.trade_task_defaults_config['fee_rate']),
            'tradeTaskDefaultSlippageRate': float(config.trade_task_defaults_config['slippage_rate']),
            'tradeTaskDefaultDailyLossStopEnabled': bool(config.trade_task_defaults_config['daily_loss_stop_enabled']),
            'tradeTaskDefaultDailyLossStopThreshold': float(config.trade_task_defaults_config['daily_loss_stop_threshold']),
            'tradeFlowFeedEnabled': bool((config.trade_market_feeds_config.get('trade_flow') or {}).get('enabled', True)),
            'tradeFlowFeedFreshnessSeconds': int((config.trade_market_feeds_config.get('trade_flow') or {}).get('freshness_seconds', 120)),
            'tradeFlowFeedLookbackTrades': int((config.trade_market_feeds_config.get('trade_flow') or {}).get('lookback_trades', 200)),
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
        api_key = str(gpt_params.get('api_key', self.config.gpt_api_key) or '')
        return {
            'gptProvider': gpt_params.get('provider', self.config.gpt_provider),
            'gptModel': gpt_params.get('model', self.config.gpt_model),
            'gptApiKey': self._mask_secret(api_key),
            'gptBaseUrl': str(gpt_params.get('base_url', self.config.gpt_base_url) or ''),
            'hasGptApiKey': bool(api_key),
            'gptApiKeyMasked': self._mask_secret(api_key),
            'persistPosition': persistence_params.get('persist_position', self.config.trade_persistence_config['persist_position']),
            'restorePositionOnStartup': persistence_params.get(
                'restore_position_on_startup',
                self.config.trade_persistence_config['restore_position_on_startup'],
            ),
            'tradeTaskDefaultFeeRate': trade_params.get('task_defaults', {}).get('fee_rate', self.config.trade_task_defaults_config['fee_rate']),
            'tradeTaskDefaultSlippageRate': trade_params.get('task_defaults', {}).get('slippage_rate', self.config.trade_task_defaults_config['slippage_rate']),
            'tradeTaskDefaultDailyLossStopEnabled': trade_params.get('task_defaults', {}).get(
                'daily_loss_stop_enabled',
                self.config.trade_task_defaults_config['daily_loss_stop_enabled'],
            ),
            'tradeTaskDefaultDailyLossStopThreshold': trade_params.get('task_defaults', {}).get(
                'daily_loss_stop_threshold',
                self.config.trade_task_defaults_config['daily_loss_stop_threshold'],
            ),
            'tradeFlowFeedEnabled': trade_params.get('market_feeds', {}).get('trade_flow', {}).get(
                'enabled',
                self.config.trade_market_feeds_config['trade_flow']['enabled'],
            ),
            'tradeFlowFeedFreshnessSeconds': trade_params.get('market_feeds', {}).get('trade_flow', {}).get(
                'freshness_seconds',
                self.config.trade_market_feeds_config['trade_flow']['freshness_seconds'],
            ),
            'tradeFlowFeedLookbackTrades': trade_params.get('market_feeds', {}).get('trade_flow', {}).get(
                'lookback_trades',
                self.config.trade_market_feeds_config['trade_flow']['lookback_trades'],
            ),
            'supportedSymbols': backtest_params.get('supported_symbols', self.config.backtest_config['supported_symbols']),
            'supportedTimeframes': backtest_params.get('supported_timeframes', self.config.backtest_config['supported_timeframes']),
            'defaultSymbol': backtest_params.get('default_symbol', self.config.backtest_config['default_symbol']),
            'defaultTimeframe': backtest_params.get('default_timeframe', self.config.backtest_config['default_timeframe']),
            'downloadTimerange': backtest_params.get('download_timerange', self.config.backtest_config['download_timerange']),
            'dataFormatOhlcv': backtest_params.get('data_format_ohlcv', self.config.backtest_config['data_format_ohlcv']),
            'exportArchiveFormat': backtest_params.get('export_archive_format', self.config.backtest_config['export_archive_format']),
        }

    def _normalize_editable_settings(self, editable: dict[str, Any], current_params: dict[str, Any] | None = None) -> dict[str, Any]:
        # 这里把前端 editable payload 归一化为数据库持久化结构。
        # 其中 gptApiKey 的空值、统一占位符或当前掩码值都表示“保留旧密钥”，而不是清空。
        provider = str(editable.get('gptProvider') or '').strip()
        if provider not in SUPPORTED_GPT_PROVIDERS:
            raise ValidationError('GPT 提供方仅支持 deepseek 或 openai')
        model = str(editable.get('gptModel') or '').strip()
        if not model:
            raise ValidationError('GPT 模型名称不能为空')
        current_gpt_params = dict((current_params or {}).get('gpt') or {})
        existing_api_key = str(current_gpt_params.get('api_key', self.config.gpt_api_key) or '').strip()
        raw_api_key = str(editable.get('gptApiKey') or '').strip()
        masked_existing_api_key = self._mask_secret(existing_api_key)
        if raw_api_key in {'', GPT_API_KEY_MASK_PLACEHOLDER, masked_existing_api_key}:
            logging.warning('系统设置保存未替换 GPT API Key，继续保留已存在密钥')
            gpt_api_key = existing_api_key
        else:
            gpt_api_key = raw_api_key
        gpt_base_url = str(editable.get('gptBaseUrl') or '').strip()
        persist_position = editable.get('persistPosition')
        if not isinstance(persist_position, bool):
            raise ValidationError('是否持久化当前持仓必须是布尔值')
        restore_position_on_startup = editable.get('restorePositionOnStartup')
        if not isinstance(restore_position_on_startup, bool):
            raise ValidationError('是否在启动时恢复持仓必须是布尔值')
        trade_task_default_fee_rate = self._normalize_non_negative_number(editable.get('tradeTaskDefaultFeeRate'), '交易任务默认手续费率')
        trade_task_default_slippage_rate = self._normalize_non_negative_number(editable.get('tradeTaskDefaultSlippageRate'), '交易任务默认滑点率')
        trade_task_default_daily_loss_stop_enabled = editable.get('tradeTaskDefaultDailyLossStopEnabled')
        if not isinstance(trade_task_default_daily_loss_stop_enabled, bool):
            raise ValidationError('是否启用交易任务默认单日亏损停机必须是布尔值')
        trade_task_default_daily_loss_stop_threshold = self._normalize_non_negative_number(
            editable.get('tradeTaskDefaultDailyLossStopThreshold'),
            '交易任务默认单日亏损停机阈值',
        )
        if trade_task_default_daily_loss_stop_enabled and trade_task_default_daily_loss_stop_threshold <= 0:
            raise ValidationError('启用交易任务默认单日亏损停机时，阈值必须大于 0')
        trade_flow_feed_enabled = editable.get('tradeFlowFeedEnabled')
        if not isinstance(trade_flow_feed_enabled, bool):
            raise ValidationError('是否启用成交流 feed 必须是布尔值')
        trade_flow_feed_freshness_seconds = self._normalize_positive_int(
            editable.get('tradeFlowFeedFreshnessSeconds'),
            '成交流 feed 新鲜度秒数',
        )
        trade_flow_feed_lookback_trades = self._normalize_positive_int(
            editable.get('tradeFlowFeedLookbackTrades'),
            '成交流 feed 回看成交数',
        )
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
                'api_key': gpt_api_key,
                'base_url': gpt_base_url,
            },
            'trade': {
                'persistence': {
                    'persist_position': persist_position,
                    'restore_position_on_startup': restore_position_on_startup,
                },
                'task_defaults': {
                    'fee_rate': trade_task_default_fee_rate,
                    'slippage_rate': trade_task_default_slippage_rate,
                    'daily_loss_stop_enabled': trade_task_default_daily_loss_stop_enabled,
                    'daily_loss_stop_threshold': trade_task_default_daily_loss_stop_threshold,
                },
                'market_feeds': {
                    'trade_flow': {
                        'enabled': trade_flow_feed_enabled,
                        'freshness_seconds': trade_flow_feed_freshness_seconds,
                        'lookback_trades': trade_flow_feed_lookback_trades,
                    },
                },
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
    def _normalize_non_negative_number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f'{label}必须是数字')
        normalized = float(value)
        if normalized < 0:
            raise ValidationError(f'{label}不能小于 0')
        return normalized

    @staticmethod
    def _normalize_positive_int(value: Any, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f'{label}必须是正整数')
        normalized = int(value)
        if normalized <= 0:
            raise ValidationError(f'{label}必须大于 0')
        return normalized

    @staticmethod
    def _mask_secret(value: str) -> str:
        # 仅用于页面回显“已配置密钥”的状态，不承担加密或安全存储职责。
        secret = str(value or '').strip()
        if not secret:
            return ''
        if len(secret) <= 8:
            return GPT_API_KEY_MASK_PLACEHOLDER
        return f'{secret[:3]}****{secret[-4:]}'

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
            logging.warning('拒绝访问越界日志文件路径: %s', normalized)
            raise ValidationError('日志文件路径非法')
        if not path.exists() or not path.is_file():
            raise ValidationError(f'未找到日志文件：{normalized}')
        if path.suffix.lower() != '.log':
            logging.warning('拒绝读取非 .log 文件: %s', normalized)
            raise ValidationError('当前仅支持查看 .log 日志文件')
        return path

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
