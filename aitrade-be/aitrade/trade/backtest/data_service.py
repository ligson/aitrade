from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Callable

from ...web.exceptions import ValidationError
from .engine import BacktestEngine
from .freqtrade_client import FreqtradeClient


class BacktestDataService:
    def __init__(self, backtest_config: dict):
        self.backtest_config = backtest_config
        self.freqtrade = FreqtradeClient(backtest_config)
        self.supported_symbols = list(backtest_config.get('supported_symbols') or [])
        self.supported_timeframes = list(backtest_config.get('supported_timeframes') or [backtest_config['default_timeframe']])
        self.default_symbol = str(backtest_config['default_symbol'])
        self.default_timeframe = str(backtest_config['default_timeframe'])
        self.download_timerange = str(backtest_config['download_timerange'])
        self.data_format_ohlcv = str(backtest_config['data_format_ohlcv'])
        self.export_archive_format = str(backtest_config.get('export_archive_format') or 'zip')

    def get_data_options(self) -> dict[str, Any]:
        return {
            'supportedSymbols': self.supported_symbols,
            'supportedTimeframes': self.supported_timeframes,
            'defaultSymbol': self.default_symbol,
            'defaultTimeframe': self.default_timeframe,
            'dataFormatOhlcv': self.data_format_ohlcv,
            'downloadMode': 'full',
            'archiveFormat': self.export_archive_format,
        }

    def ensure_supported_symbol(self, pair: str) -> None:
        if pair not in self.supported_symbols:
            raise ValidationError(f'当前仅支持以下交易对历史数据：{"、".join(self.supported_symbols)}')

    def ensure_supported_timeframe(self, timeframe: str) -> None:
        if timeframe not in self.supported_timeframes:
            raise ValidationError(f'当前仅支持以下周期历史数据：{"、".join(self.supported_timeframes)}')

    def get_data_status(self, pair: str | None = None, timeframe: str | None = None, timerange: str | None = None) -> dict[str, Any]:
        return self.freqtrade.get_data_status(pair=pair, timeframe=timeframe, timerange=timerange).to_dict()

    def download_data(self, pair: str | None = None, timeframe: str | None = None, timerange: str | None = None) -> dict[str, Any]:
        pair_value = str(pair or self.default_symbol).strip()
        timeframe_value = str(timeframe or self.default_timeframe).strip()
        self.ensure_supported_symbol(pair_value)
        self.ensure_supported_timeframe(timeframe_value)
        return self.freqtrade.download_data(pair=pair_value, timeframe=timeframe_value, timerange=timerange or self.download_timerange)

    def load_bars(self, pair: str, timeframe: str) -> list[list[Any]]:
        rows = self.freqtrade.load_ohlcv_rows(pair=pair, timeframe=timeframe)
        normalized_rows: list[list[Any]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            normalized_rows.append(row[:6])
        if not normalized_rows:
            raise ValidationError('历史数据为空，无法执行回测')
        return normalized_rows

    @staticmethod
    def _symbol_to_token(symbol: str) -> str:
        return symbol.replace('/', '_').replace(':', '_')

    @staticmethod
    def _token_to_symbol(token: str) -> str:
        parts = [part for part in token.split('_') if part]
        if len(parts) < 2:
            raise ValidationError(f'历史数据文件名不符合约定：{token}')
        return f'{parts[0]}/{parts[1]}'

    def parse_data_filename(self, filename: str) -> dict[str, Any]:
        if filename.endswith('.json.gz'):
            name_without_ext = filename[:-8]
            format_value = 'jsongz'
        elif filename.endswith('.json'):
            name_without_ext = filename[:-5]
            format_value = 'json'
        else:
            raise ValidationError(f'历史数据文件格式不受支持：{filename}')
        if '-' not in name_without_ext:
            raise ValidationError(f'历史数据文件名不符合约定：{filename}')
        pair_token, timeframe = name_without_ext.rsplit('-', 1)
        if not pair_token or not timeframe:
            raise ValidationError(f'历史数据文件名不符合约定：{filename}')
        symbol = self._token_to_symbol(pair_token)
        return {
            'filename': filename,
            'symbol': symbol,
            'timeframe': timeframe,
            'format': format_value,
        }

    def resolve_data_file(self, filename: str) -> Path:
        data_dir = Path(self.ensure_data_dir(self.backtest_config))
        path = (data_dir / filename).resolve()
        if path.parent != data_dir:
            raise ValidationError('历史数据文件路径非法')
        if not path.exists() or not path.is_file():
            raise ValidationError(f'未找到历史数据文件：{filename}')
        return path

    def inspect_data_file(self, filename: str) -> dict[str, Any]:
        file_path = self.resolve_data_file(filename)
        parsed = self.parse_data_filename(file_path.name)
        rows = self.load_bars(parsed['symbol'], parsed['timeframe'])
        first_bar = rows[0]
        last_bar = rows[-1]
        timerange_from = datetime.fromtimestamp(int(first_bar[0]) / 1000, tz=timezone.utc).isoformat()
        timerange_to = datetime.fromtimestamp(int(last_bar[0]) / 1000, tz=timezone.utc).isoformat()
        stat = file_path.stat()
        return {
            'filename': file_path.name,
            'symbol': parsed['symbol'],
            'timeframe': parsed['timeframe'],
            'format': parsed['format'],
            'path': str(file_path),
            'size': stat.st_size,
            'modifiedAt': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            'timerangeFrom': timerange_from,
            'timerangeTo': timerange_to,
            'timerangeLabel': f'{timerange_from} ~ {timerange_to}',
            'available': True,
            'sourceType': 'local',
        }

    def list_data_files(self, symbol: str = '', timeframe: str = '', keyword: str = '') -> list[dict[str, Any]]:
        data_dir = Path(self.ensure_data_dir(self.backtest_config))
        rows: list[dict[str, Any]] = []
        for path in sorted(data_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            if not (path.name.endswith('.json') or path.name.endswith('.json.gz')):
                continue
            try:
                item = self.inspect_data_file(path.name)
            except Exception:
                continue
            if symbol and item['symbol'] != symbol:
                continue
            if timeframe and item['timeframe'] != timeframe:
                continue
            if keyword:
                haystack = f"{item['filename']} {item['symbol']} {item['timeframe']}".lower()
                if keyword.lower() not in haystack:
                    continue
            rows.append(item)
        return rows

    def export_data_files(self, filenames: list[str]) -> tuple[str, bytes]:
        if not filenames:
            raise ValidationError('请至少选择一个历史数据文件')
        if self.export_archive_format != 'zip':
            raise ValidationError('当前仅支持 zip 压缩包导出')
        buffer = io.BytesIO()
        manifest_files: list[dict[str, Any]] = []
        unique_filenames = list(dict.fromkeys(filenames))
        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as archive:
            for filename in unique_filenames:
                file_path = self.resolve_data_file(filename)
                archive.write(file_path, arcname=file_path.name)
                manifest_files.append(self.inspect_data_file(file_path.name))
            manifest = {
                'exportedAt': datetime.now(timezone.utc).isoformat(),
                'archiveFormat': self.export_archive_format,
                'files': manifest_files,
            }
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        archive_name = f'backtest-data-export-{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}.zip'
        return archive_name, buffer.getvalue()

    def import_data_archive(self, archive_bytes: bytes, overwrite: bool = False) -> dict[str, Any]:
        data_dir = Path(self.ensure_data_dir(self.backtest_config))
        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            for info in archive.infolist():
                if info.is_dir() or info.filename == 'manifest.json':
                    continue
                name = Path(info.filename).name
                if name != info.filename:
                    raise ValidationError('压缩包内文件路径非法')
                parsed = self.parse_data_filename(name)
                self.ensure_supported_symbol(parsed['symbol'])
                self.ensure_supported_timeframe(parsed['timeframe'])
                target = data_dir / name
                if target.exists() and not overwrite:
                    skipped.append({'filename': name, 'reason': '文件已存在'})
                    continue
                content = archive.read(info)
                target.write_bytes(content)
                imported.append(self.inspect_data_file(name))
        return {
            'imported': imported,
            'skipped': skipped,
            'failed': [],
        }

    def delete_data_file(self, filename: str) -> None:
        path = self.resolve_data_file(filename)
        path.unlink(missing_ok=False)

    def run_backtest(
        self,
        strategy_type: str,
        symbol: str,
        timeframe: str,
        timerange_from: str,
        timerange_to: str,
        strategy_params: dict[str, Any],
        initial_balance: float,
        fee_rate: float,
        data_file: str | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        if strategy_type != 'btc_spot_breakout':
            raise ValidationError('当前仅支持 btc_spot_breakout 策略离线回测')
        bars = self.load_bars(pair=symbol, timeframe=timeframe)
        engine = BacktestEngine(fee_rate=fee_rate, initial_balance=initial_balance)
        result = engine.run_breakout_backtest(
            bars=bars,
            symbol=symbol,
            timeframe=timeframe,
            strategy_params=strategy_params,
            timerange_from=timerange_from,
            timerange_to=timerange_to,
            should_stop=should_stop,
            on_progress=on_progress,
        )
        if data_file:
            result['dataSource'] = self.inspect_data_file(data_file)
        else:
            status = self.get_data_status(pair=symbol, timeframe=timeframe)
            result['dataSource'] = status
        return result

    @staticmethod
    def normalize_timerange(value: str | None, fallback: str) -> tuple[str, str]:
        raw = (value or fallback).strip()
        if not raw or '-' not in raw:
            raise ValidationError('时间范围格式不正确，必须是 YYYYMMDD-YYYYMMDD 或 YYYYMMDD-')
        start_raw, end_raw = raw.split('-', 1)
        if not start_raw:
            raise ValidationError('时间范围开始日期不能为空')
        start = datetime.strptime(start_raw, '%Y%m%d').replace(tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) if not end_raw else datetime.strptime(end_raw, '%Y%m%d').replace(tzinfo=timezone.utc)
        if end < start:
            raise ValidationError('时间范围结束时间不能早于开始时间')
        return start.isoformat(), end.isoformat()

    @staticmethod
    def extract_timerange(payload: dict[str, Any], fallback: str) -> tuple[str, str, str]:
        timerange = str(payload.get('timerange') or fallback).strip()
        timerange_from, timerange_to = BacktestDataService.normalize_timerange(timerange, fallback=fallback)
        return timerange, timerange_from, timerange_to

    @staticmethod
    def serialize_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def ensure_data_dir(backtest_config: dict) -> str:
        path = Path(backtest_config['data_dir']).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
