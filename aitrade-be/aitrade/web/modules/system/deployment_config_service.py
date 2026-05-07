from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ....config.config_file import Config
from ....config.config_file import ConfigValidationError
from ....config.path_utils import build_managed_data_paths
from ....config.path_utils import resolve_data_root_dir
from ...exceptions import ValidationError


class DeploymentConfigService:
    """管理直接写回 config.yaml 的部署级配置。"""

    def __init__(self, config: Config):
        self.config = config
        self.config_path = Path(config.config_path or './config.yaml').resolve()

    def get_settings(self) -> dict[str, Any]:
        file_config = self._load_file_config()
        file_runtime = self._serialize_runtime(file_config)
        runtime = self._serialize_runtime(self.config)
        return {
            'configFilePath': str(self.config_path),
            'editable': self._serialize_editable(file_config),
            'derivedPaths': dict(file_config.managed_data_paths),
            'runtime': runtime,
            'compatibilityStatus': file_config.data_root_mode,
            'compatibilityMessage': self._build_compatibility_message(file_config),
            'restartRequired': file_runtime != runtime,
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        editable = payload.get('editable')
        if not isinstance(editable, dict):
            raise ValidationError('部署设置内容不能为空')

        normalized_root = self._normalize_payload(editable)
        current_file_config = self._load_file_config()
        current_runtime = self._serialize_runtime(current_file_config)
        target_paths = build_managed_data_paths(normalized_root)
        changed_keys = [key for key, value in target_paths.items() if current_runtime.get(key) != value]
        if current_file_config.data_root_mode != 'managed' or current_file_config.data_root_dir != normalized_root:
            if 'dataRootDir' not in changed_keys:
                changed_keys.insert(0, 'dataRootDir')
        if not changed_keys:
            return {
                **self.get_settings(),
                'changedKeys': [],
                'message': '部署设置未发生变化',
            }

        config_data = self._load_raw_config_data()
        app_cfg = self._require_mapping(config_data, 'app', 'app')
        app_cfg['data_root_dir'] = normalized_root
        app_cfg.pop('log_dir', None)

        trade_cfg = self._require_mapping(app_cfg, 'trade', 'app.trade')
        persistence_cfg = self._require_mapping(trade_cfg, 'persistence', 'app.trade.persistence')
        persistence_cfg.pop('database_url', None)
        persistence_cfg.pop('sqlite_path', None)

        backtest_cfg = self._require_mapping(app_cfg, 'backtest', 'app.backtest')
        backtest_cfg.pop('data_dir', None)
        backtest_cfg.pop('user_data_dir', None)

        try:
            validated = Config.from_dict(config_data, mode='web')
        except ConfigValidationError as exc:
            raise ValidationError(str(exc)) from exc

        validated_app_cfg = self._require_mapping(config_data, 'app', 'app')
        validated_app_cfg['data_root_dir'] = validated.data_root_dir

        with self.config_path.open('w', encoding='utf-8') as file:
            yaml.safe_dump(config_data, file, allow_unicode=True, sort_keys=False)

        return {
            **self.get_settings(),
            'changedKeys': changed_keys,
            'message': '部署设置已写回 config.yaml，需重启后端后生效',
        }

    def _load_file_config(self) -> Config:
        try:
            return Config.from_yaml(str(self.config_path), mode='web')
        except ConfigValidationError as exc:
            raise ValidationError(str(exc)) from exc

    def _load_raw_config_data(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ValidationError(f'配置文件不存在：{self.config_path}')
        try:
            with self.config_path.open('r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}
        except yaml.YAMLError as exc:
            raise ValidationError(f'config.yaml YAML 格式错误：{exc}') from exc
        if not isinstance(data, dict):
            raise ValidationError('config.yaml 顶层结构必须是对象')
        return data

    @staticmethod
    def _serialize_editable(config: Config) -> dict[str, str]:
        return {
            'dataRootDir': config.data_root_dir,
        }

    @staticmethod
    def _serialize_runtime(config: Config) -> dict[str, str]:
        return {
            'dataRootDir': config.data_root_dir,
            'databaseUrl': config.trade_persistence_config['database_url'],
            'backtestDataDir': config.backtest_config['data_dir'],
            'freqtradeUserDataDir': config.backtest_config['user_data_dir'],
            'appLogDir': config.log_dir,
        }

    def _normalize_payload(self, editable: dict[str, Any]) -> str:
        data_root_dir = str(editable.get('dataRootDir') or '').strip()
        if not data_root_dir:
            raise ValidationError('数据根目录不能为空')
        normalized_root = resolve_data_root_dir(data_root_dir)
        try:
            candidate = self._load_raw_config_data()
            app_cfg = self._require_mapping(candidate, 'app', 'app')
            app_cfg['data_root_dir'] = normalized_root
            app_cfg.pop('log_dir', None)
            trade_cfg = self._require_mapping(app_cfg, 'trade', 'app.trade')
            persistence_cfg = self._require_mapping(trade_cfg, 'persistence', 'app.trade.persistence')
            persistence_cfg.pop('database_url', None)
            persistence_cfg.pop('sqlite_path', None)
            backtest_cfg = self._require_mapping(app_cfg, 'backtest', 'app.backtest')
            backtest_cfg.pop('data_dir', None)
            backtest_cfg.pop('user_data_dir', None)
            validated = Config.from_dict(candidate, mode='web')
        except ConfigValidationError as exc:
            raise ValidationError(str(exc)) from exc
        return validated.data_root_dir

    @staticmethod
    def _build_compatibility_message(config: Config) -> str:
        if config.data_root_mode == 'managed':
            return '当前已使用单一数据根目录，数据库、日志与历史数据目录都会按该根目录自动规划。'
        if config.data_root_mode == 'legacy_inferred':
            return '当前仍在兼容读取旧版分散字段，但已经推导出统一根目录；保存后会收敛为单根目录配置。'
        if config.data_root_mode == 'external_database':
            return '当前数据库仍使用外部连接地址；页面保存根目录后，会切换为根目录下的本地 SQLite，并统一目录结构。'
        return '当前仍在兼容读取旧版分散路径；页面保存根目录后，会把数据库、日志与历史数据目录统一收敛到单根目录。'

    @staticmethod
    def _require_mapping(container: dict[str, Any], key: str, path: str) -> dict[str, Any]:
        value = container.get(key)
        if value is None:
            value = {}
            container[key] = value
        if not isinstance(value, dict):
            raise ValidationError(f'{path} 必须是对象/字典')
        return value
