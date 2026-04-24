from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from ....config.config_file import Config
from ....config.log_config import resolve_log_dir
from ...exceptions import ValidationError


class SystemService:
    def __init__(self, config: Config):
        self.config = config
        self.log_dir = Path(resolve_log_dir()).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_settings(self) -> dict[str, Any]:
        backtest_config = self.config.backtest_config
        backtest_data_dir = Path(backtest_config['data_dir']).expanduser().resolve()
        freqtrade_user_data_dir = Path(backtest_config['user_data_dir']).expanduser().resolve()
        return {
            'backtestDataDir': str(backtest_data_dir),
            'freqtradeUserDataDir': str(freqtrade_user_data_dir),
            'appLogDir': str(self.log_dir),
            'supportedTimeframes': list(backtest_config.get('supported_timeframes') or []),
            'defaultTimeframe': str(backtest_config['default_timeframe']),
            'dataFormatOhlcv': str(backtest_config['data_format_ohlcv']),
            'exportArchiveFormat': str(backtest_config['export_archive_format']),
            'downloadTimerange': str(backtest_config['download_timerange']),
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
