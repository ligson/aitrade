#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
COMMAND="${1:-latest}"
ARG1="${2:-}"
ARG2="${3:-}"

cd "$ROOT_DIR"

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

run_python() {
    if [ -x "$PYTHON_BIN" ]; then
        "$PYTHON_BIN" "$@"
        return
    fi
    error "未找到 uv 环境中的 Python：$PYTHON_BIN"
    error "原因：环境尚未初始化完成。"
    error "建议：先执行 bash init-env.sh"
    exit 1
}

run_python - "$ROOT_DIR" "$COMMAND" "$ARG1" "$ARG2" <<'PY'
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"[ERROR] 缺少 Python 依赖：{exc.name}\n[ERROR] 建议：先执行 bash init-env.sh"
    ) from exc

root_dir = Path(sys.argv[1])
sys.path.insert(0, str(root_dir))

try:
    from aitrade.config.config_file import DEFAULT_TRADE_PERSISTENCE_CONFIG
    from aitrade.trade.trading_system.trade_store_factory import create_trade_store
    from aitrade.trade.trading_system.trade_store_factory import summarize_database_target
except ModuleNotFoundError as exc:
    raise SystemExit(
        f"[ERROR] 缺少 Python 依赖：{exc.name}\n[ERROR] 建议：先执行 bash init-env.sh"
    ) from exc


def parse_limit(raw, default=20):
    if raw == '':
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"[ERROR] limit 必须是整数，收到: {raw}") from exc
    if value <= 0:
        raise SystemExit(f"[ERROR] limit 必须大于 0，收到: {value}")
    return value


def require_mapping(value, path):
    if not isinstance(value, dict):
        raise SystemExit(f"[ERROR] 配置项 {path} 必须是对象/字典")
    return value


def require_non_empty_string(value, path):
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"[ERROR] 配置项 {path} 必须是非空字符串")
    return value.strip()


def load_persistence_config(config_path: Path):
    if not config_path.exists():
        raise SystemExit(f"[ERROR] 未找到配置文件：{config_path}\n[ERROR] 建议：先复制 config.example.yaml 为 config.yaml 并完成配置。")

    with config_path.open('r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise SystemExit('[ERROR] config.yaml 顶层结构必须是对象，且至少包含 app 配置')

    app_cfg = require_mapping(config.get('app'), 'app')
    trade_cfg = require_mapping(app_cfg.get('trade'), 'app.trade')
    persistence_overrides = trade_cfg.get('persistence', {})
    if persistence_overrides is None:
        persistence_overrides = {}
    if not isinstance(persistence_overrides, dict):
        raise SystemExit('[ERROR] 配置项 app.trade.persistence 必须是对象/字典')

    persistence_config = dict(DEFAULT_TRADE_PERSISTENCE_CONFIG)
    persistence_config.update(persistence_overrides)
    database_url = persistence_overrides.get('database_url')
    sqlite_path = persistence_overrides.get('sqlite_path')
    if database_url is None and sqlite_path is not None:
        database_url = f"sqlite:///{require_non_empty_string(sqlite_path, 'app.trade.persistence.sqlite_path')}"
    persistence_config['database_url'] = require_non_empty_string(
        database_url or persistence_config.get('database_url'),
        'app.trade.persistence.database_url',
    )
    return persistence_config


def print_rows(rows):
    if not rows:
        print('[INFO] 没有查询到记录')
        return

    headers = list(rows[0].keys())
    widths = {header: len(header) for header in headers}
    normalized_rows = []
    for row in rows:
        normalized = {}
        for header in headers:
            value = row[header]
            text = '' if value is None else str(value)
            normalized[header] = text
            widths[header] = max(widths[header], len(text))
        normalized_rows.append(normalized)

    header_line = ' | '.join(header.ljust(widths[header]) for header in headers)
    separator = '-+-'.join('-' * widths[header] for header in headers)
    print(header_line)
    print(separator)
    for row in normalized_rows:
        print(' | '.join(row[header].ljust(widths[header]) for header in headers))


config_path = root_dir / 'config.yaml'
command, arg1, arg2 = sys.argv[2:5]
persistence_config = load_persistence_config(config_path)
if persistence_config['database_url'].startswith('sqlite:///'):
    db_path = Path(persistence_config['database_url'][10:])
    if not db_path.is_absolute():
        db_path = root_dir / db_path
    if not db_path.exists():
        raise SystemExit(f"[ERROR] 未找到 SQLite 数据库：{db_path}\n[ERROR] 建议：先运行交易程序生成交易记录后再查询。")
store = create_trade_store(persistence_config)
print(f"[INFO] 当前持久化目标: {summarize_database_target(store.database_url)}")

try:
    if command == 'latest':
        limit = parse_limit(arg1)
        print(f'[INFO] 查看最近 {limit} 条交易记录')
        records = store.query_trade_records(limit=limit)
        rows = [
            {
                'id': row['id'],
                'created_at': row['created_at'],
                'strategy': row['strategy'],
                'trigger_source': row['trigger_source'],
                'side': row['side'],
                'market_price': row['market_price'],
                'requested_amount': row['requested_amount'],
                'result': row['result'],
                'result_reason': row['result_reason'],
                'order_id': row['order_id'],
            }
            for row in records
        ]
    elif command == 'strategy':
        if not arg1:
            raise SystemExit('[ERROR] 请提供策略名，例如：bash query-trades.sh strategy gpt 20')
        limit = parse_limit(arg2)
        print(f'[INFO] 按策略 {arg1} 查看最近 {limit} 条记录')
        records = store.query_trade_records(limit=limit, strategy=arg1)
        rows = [
            {
                'id': row['id'],
                'created_at': row['created_at'],
                'strategy': row['strategy'],
                'side': row['side'],
                'market_price': row['market_price'],
                'requested_amount': row['requested_amount'],
                'result': row['result'],
                'result_reason': row['result_reason'],
            }
            for row in records
        ]
    elif command == 'side':
        if not arg1:
            raise SystemExit('[ERROR] 请提供方向，例如：bash query-trades.sh side buy 20')
        limit = parse_limit(arg2)
        print(f'[INFO] 按方向 {arg1} 查看最近 {limit} 条记录')
        records = store.query_trade_records(limit=limit, side=arg1)
        rows = [
            {
                'id': row['id'],
                'created_at': row['created_at'],
                'strategy': row['strategy'],
                'side': row['side'],
                'market_price': row['market_price'],
                'requested_amount': row['requested_amount'],
                'result': row['result'],
                'result_reason': row['result_reason'],
            }
            for row in records
        ]
    elif command == 'failed':
        limit = parse_limit(arg1)
        print(f'[INFO] 查看最近 {limit} 条异常或风控拒绝记录')
        records = store.query_trade_records(limit=limit, results=['failed', 'risk_rejected'])
        rows = [
            {
                'id': row['id'],
                'created_at': row['created_at'],
                'strategy': row['strategy'],
                'side': row['side'],
                'result': row['result'],
                'result_reason': row['result_reason'],
                'error_message': row['error_message'],
            }
            for row in records
        ]
    elif command == 'position':
        print('[INFO] 查看当前持仓状态')
        positions = store.query_position_states()
        rows = [
            {
                'symbol': row['symbol'],
                'strategy': row['strategy'],
                'entry_time': row['entry_time'],
                'entry_price': row['entry_price'],
                'amount': row['amount'],
                'stop_loss': row['stop_loss'],
                'initial_stop_loss': row['initial_stop_loss'],
                'trailing_stop_price': row['trailing_stop_price'],
                'highest_price': row['highest_price'],
                'highest_close': row['highest_close'],
                'updated_at': row['updated_at'],
            }
            for row in positions
        ]
    else:
        raise SystemExit(f'[ERROR] 不支持的命令：{command}\n[ERROR] 支持的命令：latest | strategy | side | failed | position')

    print_rows(rows)
finally:
    store.close()
PY
