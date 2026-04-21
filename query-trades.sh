#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_PATH="$ROOT_DIR/.aitrade/trades.sqlite3"
COMMAND="${1:-latest}"
ARG1="${2:-}"
ARG2="${3:-}"

info() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

require_python3() {
    if ! command -v python3 >/dev/null 2>&1; then
        error "未检测到 python3。"
        error "建议：先安装 Python 3，再执行 bash query-trades.sh"
        exit 1
    fi
}

require_db() {
    if [ ! -f "$DB_PATH" ]; then
        error "未找到 SQLite 数据库：$DB_PATH"
        error "建议：先运行交易程序生成交易记录后再查询。"
        exit 1
    fi
}

require_python3
require_db

python3 - "$DB_PATH" "$COMMAND" "$ARG1" "$ARG2" <<'PY'
import sqlite3
import sys


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


db_path, command, arg1, arg2 = sys.argv[1:5]
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

if command == 'latest':
    limit = parse_limit(arg1)
    print(f'[INFO] 查看最近 {limit} 条交易记录')
    rows = conn.execute(
        '''
        SELECT id, created_at, strategy, trigger_source, side, market_price, requested_amount, result, result_reason, order_id
        FROM trade_records
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (limit,),
    ).fetchall()
elif command == 'strategy':
    if not arg1:
        raise SystemExit('[ERROR] 请提供策略名，例如：bash query-trades.sh strategy gpt 20')
    limit = parse_limit(arg2)
    print(f'[INFO] 按策略 {arg1} 查看最近 {limit} 条记录')
    rows = conn.execute(
        '''
        SELECT id, created_at, strategy, side, market_price, requested_amount, result, result_reason
        FROM trade_records
        WHERE strategy = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (arg1, limit),
    ).fetchall()
elif command == 'side':
    if not arg1:
        raise SystemExit('[ERROR] 请提供方向，例如：bash query-trades.sh side buy 20')
    limit = parse_limit(arg2)
    print(f'[INFO] 按方向 {arg1} 查看最近 {limit} 条记录')
    rows = conn.execute(
        '''
        SELECT id, created_at, strategy, side, market_price, requested_amount, result, result_reason
        FROM trade_records
        WHERE side = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (arg1, limit),
    ).fetchall()
elif command == 'failed':
    limit = parse_limit(arg1)
    print(f'[INFO] 查看最近 {limit} 条异常或风控拒绝记录')
    rows = conn.execute(
        '''
        SELECT id, created_at, strategy, side, result, result_reason, error_message
        FROM trade_records
        WHERE result IN ('failed', 'risk_rejected')
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (limit,),
    ).fetchall()
elif command == 'position':
    print('[INFO] 查看当前持仓状态')
    rows = conn.execute(
        '''
        SELECT symbol, strategy, entry_time, entry_price, amount, stop_loss, initial_stop_loss, trailing_stop_price, highest_price, highest_close, updated_at
        FROM position_state
        ORDER BY updated_at DESC
        '''
    ).fetchall()
else:
    raise SystemExit(f'[ERROR] 不支持的命令：{command}\n[ERROR] 支持的命令：latest | strategy | side | failed | position')

print_rows(rows)
PY
