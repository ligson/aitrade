from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import cast


@dataclass
class DownloadedDataStatus:
    available: bool
    pair: str
    timeframe: str
    timerange: str
    path: str
    format: str
    size: int | None = None
    modified_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'available': self.available,
            'pair': self.pair,
            'timeframe': self.timeframe,
            'timerange': self.timerange,
            'path': self.path,
            'format': self.format,
            'size': self.size,
            'modifiedAt': self.modified_at,
        }


class FreqtradeClient:
    def __init__(self, backtest_config: dict):
        self.data_dir = Path(backtest_config['data_dir']).expanduser().resolve()
        self.user_data_dir = Path(backtest_config['user_data_dir']).expanduser().resolve()
        self.default_symbol = backtest_config['default_symbol']
        self.default_timeframe = backtest_config['default_timeframe']
        self.download_timerange = backtest_config['download_timerange']
        self.freqtrade_bin = backtest_config['freqtrade_bin']
        self.data_format_ohlcv = backtest_config['data_format_ohlcv']
        self.supported_symbols = list(backtest_config.get('supported_symbols') or [self.default_symbol])
        self.proxy_enable = bool(backtest_config.get('proxy_enable', False))
        self.proxy_url = str(backtest_config.get('proxy_url') or '').strip()

    @staticmethod
    def _pair_to_filename(pair: str) -> str:
        return pair.replace('/', '_').replace(':', '_')

    def get_ohlcv_path(self, pair: str | None = None, timeframe: str | None = None) -> Path:
        pair_value = pair or self.default_symbol
        timeframe_value = timeframe or self.default_timeframe
        extension = '.json.gz' if self.data_format_ohlcv == 'jsongz' else '.json'
        return self.data_dir / f'{self._pair_to_filename(pair_value)}-{timeframe_value}{extension}'

    def get_data_status(self, pair: str | None = None, timeframe: str | None = None, timerange: str | None = None) -> DownloadedDataStatus:
        file_path = self.get_ohlcv_path(pair=pair, timeframe=timeframe)
        if not file_path.exists():
            return DownloadedDataStatus(
                available=False,
                pair=pair or self.default_symbol,
                timeframe=timeframe or self.default_timeframe,
                timerange=timerange or self.download_timerange,
                path=str(file_path),
                format=self.data_format_ohlcv,
            )
        stat = file_path.stat()
        return DownloadedDataStatus(
            available=True,
            pair=pair or self.default_symbol,
            timeframe=timeframe or self.default_timeframe,
            timerange=timerange or self.download_timerange,
            path=str(file_path),
            format=self.data_format_ohlcv,
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )

    def _resolve_freqtrade_bin(self) -> str | None:
        resolved = shutil.which(self.freqtrade_bin)
        if resolved is not None:
            return resolved

        candidate_dirs: list[Path] = [Path(sys.executable).parent, Path(sys.prefix) / 'bin']
        virtual_env = os.environ.get('VIRTUAL_ENV')
        if virtual_env:
            candidate_dirs.append(Path(virtual_env) / 'bin')

        seen: set[str] = set()
        for directory in candidate_dirs:
            key = str(directory)
            if key in seen:
                continue
            seen.add(key)
            venv_candidate = directory / self.freqtrade_bin
            if venv_candidate.is_file() and os.access(venv_candidate, os.X_OK):
                return str(venv_candidate)
        return None

    def ensure_cli_available(self) -> None:
        resolved = self._resolve_freqtrade_bin()
        if resolved is None:
            raise RuntimeError(
                f'未找到 freqtrade 命令：{self.freqtrade_bin}。请先执行 bash init-env.sh，或把 app.backtest.freqtrade_bin 改为可执行绝对路径。'
            )
        self.freqtrade_bin = resolved

    def ensure_user_data_dir(self) -> None:
        os.makedirs(self.user_data_dir, exist_ok=True)
        config_path = self.user_data_dir / 'config.json'
        ccxt_proxy_config = self._build_ccxt_proxy_config()
        default_config = {
            'dry_run': True,
            'stake_currency': 'USDT',
            'stake_amount': 'unlimited',
            'exchange': {
                'name': 'binance',
                'key': '',
                'secret': '',
                'pair_whitelist': list(self.supported_symbols),
                'pair_blacklist': [],
                'only_from_ccxt': True,
            },
        }
        if ccxt_proxy_config:
            default_config['exchange']['ccxt_config'] = dict(ccxt_proxy_config)
            default_config['exchange']['ccxt_async_config'] = dict(ccxt_proxy_config)
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding='utf-8') or '{}')
            except json.JSONDecodeError:
                existing = {}
        else:
            existing = {}
        merged = dict(default_config)
        if isinstance(existing, dict):
            merged.update(existing)
            exchange_config = dict(default_config['exchange'])
            if isinstance(existing.get('exchange'), dict):
                exchange_config.update(existing['exchange'])
            merged['exchange'] = exchange_config
        exchange_config = dict(merged.get('exchange') or {})
        for key in ('ccxt_config', 'ccxt_sync_config', 'ccxt_async_config'):
            if ccxt_proxy_config:
                exchange_config[key] = dict(ccxt_proxy_config)
            else:
                exchange_config.pop(key, None)
        merged['exchange'] = exchange_config
        config_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def _build_ccxt_proxy_config(self) -> dict[str, str]:
        if not self.proxy_enable or not self.proxy_url:
            return {}
        return {
            'httpsProxy': self.proxy_url,
            'wsProxy': self.proxy_url,
            'wssProxy': self.proxy_url,
        }

    def _build_download_env(self) -> dict[str, str] | None:
        if not self.proxy_enable or not self.proxy_url:
            return None
        env = os.environ.copy()
        env['HTTP_PROXY'] = self.proxy_url
        env['HTTPS_PROXY'] = self.proxy_url
        env['ALL_PROXY'] = self.proxy_url
        return env

    def build_download_command(self, pair: str | None = None, timeframe: str | None = None, timerange: str | None = None) -> list[str]:
        pair_value = pair or self.default_symbol
        timeframe_value = timeframe or self.default_timeframe
        timerange_value = timerange or self.download_timerange
        return [
            self.freqtrade_bin,
            'download-data',
            '--userdir',
            str(self.user_data_dir),
            '--exchange',
            'binance',
            '--trading-mode',
            'spot',
            '--pairs',
            pair_value,
            '--timeframes',
            timeframe_value,
            '--timerange',
            timerange_value,
            '--data-dir',
            str(self.data_dir),
            '--data-format-ohlcv',
            self.data_format_ohlcv,
        ]

    def _extract_error_message(self, result: subprocess.CompletedProcess[str]) -> str:
        stderr = (result.stderr or '').strip()
        stdout = (result.stdout or '').strip()
        raw = stderr or stdout or 'freqtrade 下载失败'
        if 'InvalidProxySettings' in raw:
            if self.proxy_enable and self.proxy_url:
                return f'freqtrade 下载失败：代理配置冲突，请检查统一代理地址配置（当前代理：{self.proxy_url}）'
            return 'freqtrade 下载失败：代理配置冲突，请检查 app.http_client.proxy_url'
        if 'ClientConnectorCertificateError' in raw or 'SSLCertVerificationError' in raw:
            if self.proxy_enable and self.proxy_url:
                return f'freqtrade 下载失败：访问 Binance 时出现证书校验异常，请检查代理配置或本机证书链（当前代理：{self.proxy_url}）'
            return 'freqtrade 下载失败：访问 Binance 时出现证书校验异常，请检查本机网络环境、代理配置或证书链'
        if 'ExchangeNotAvailable' in raw and 'api.binance.com' in raw:
            return 'freqtrade 下载失败：当前网络无法连接 Binance，请检查代理或外网访问能力'
        return f'freqtrade 下载失败：{raw}'

    def download_data(self, pair: str | None = None, timeframe: str | None = None, timerange: str | None = None) -> dict[str, Any]:
        self.ensure_cli_available()
        self.ensure_user_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)
        command = self.build_download_command(pair=pair, timeframe=timeframe, timerange=timerange)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=cast(dict[str, str] | None, self._build_download_env()),
        )
        if result.returncode != 0:
            raise RuntimeError(self._extract_error_message(result))
        return {
            'command': command,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'status': self.get_data_status(pair=pair, timeframe=timeframe, timerange=timerange).to_dict(),
        }

    def load_ohlcv_rows(self, pair: str | None = None, timeframe: str | None = None) -> list[list[Any]]:
        file_path = self.get_ohlcv_path(pair=pair, timeframe=timeframe)
        if not file_path.exists():
            raise FileNotFoundError(f'未找到历史数据文件：{file_path}')
        if self.data_format_ohlcv == 'jsongz':
            with gzip.open(file_path, 'rt', encoding='utf-8') as file:
                data = json.load(file)
        else:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        if not isinstance(data, list):
            raise RuntimeError('历史数据文件格式不正确，期望顶层为数组')
        return data
