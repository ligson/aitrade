#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.aitrade"
PID_FILE="$RUNTIME_DIR/aitrade.pid"
RUNTIME_FILE="$RUNTIME_DIR/runtime.env"
LOG_DIR="$ROOT_DIR/logs"
VENV_PYTHON="$ROOT_DIR/venv/bin/python"

info() {
    printf '[INFO] %s\n' "$1"
}

warn() {
    printf '[WARN] %s\n' "$1"
}

load_runtime() {
    if [ ! -f "$RUNTIME_FILE" ]; then
        return 1
    fi

    local line
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*)
                continue
                ;;
            *=*)
                local key=${line%%=*}
                local value=${line#*=}
                case "$key" in
                    PID|STARTED_AT|REPO_ROOT|PYTHON_BIN|CONFIG_PATH|LOG_DIR|LAUNCHER_LOG)
                        printf -v "$key" '%s' "$value"
                        ;;
                    *)
                        ;;
                esac
                ;;
            *)
                return 1
                ;;
        esac
    done < "$RUNTIME_FILE"

    [ -n "${PID:-}" ]
}

latest_app_log() {
    local latest
    latest=$(ls -1t "$LOG_DIR"/*.log 2>/dev/null | grep -v '/trade_' | grep -v '/launcher\.log$' | head -n 1 || true)
    if [ -n "$latest" ]; then
        printf '%s\n' "$latest"
    fi
}

latest_trade_log() {
    local latest
    latest=$(ls -1t "$LOG_DIR"/trade_*.log 2>/dev/null | head -n 1 || true)
    if [ -n "$latest" ]; then
        printf '%s\n' "$latest"
    fi
}

process_matches() {
    local pid="$1"
    local cmdline

    if ! ps -p "$pid" > /dev/null 2>&1; then
        return 1
    fi

    cmdline=$(ps -p "$pid" -o command= 2>/dev/null || true)
    if [ -z "$cmdline" ]; then
        return 1
    fi

    [[ "$cmdline" == *"$VENV_PYTHON"* && "$cmdline" == *"-m aitrade"* ]]
}

print_log_info() {
    printf '日志目录: %s\n' "$LOG_DIR"
    if [ -n "$(latest_app_log)" ]; then
        printf '最新应用日志: %s\n' "$(latest_app_log)"
    fi
    if [ -n "$(latest_trade_log)" ]; then
        printf '最新交易日志: %s\n' "$(latest_trade_log)"
    fi
}

cd "$ROOT_DIR"

if [ ! -f "$PID_FILE" ] && [ ! -f "$RUNTIME_FILE" ]; then
    info "当前状态: stopped"
    printf '项目目录: %s\n' "$ROOT_DIR"
    print_log_info
    exit 0
fi

PID=''
STARTED_AT=''
REPO_ROOT=''
PYTHON_BIN=''
CONFIG_PATH=''
LAUNCHER_LOG=''
if ! load_runtime; then
    warn "当前状态: stale"
    warn "原因：运行态文件缺失或损坏。"
    printf '项目目录: %s\n' "$ROOT_DIR"
    print_log_info
    printf '建议操作: bash stop.sh\n'
    exit 0
fi

if process_matches "$PID"; then
    info "当前状态: running"
    printf 'PID: %s\n' "$PID"
    printf '启动时间: %s\n' "$STARTED_AT"
    printf '项目目录: %s\n' "${REPO_ROOT:-$ROOT_DIR}"
    printf '配置文件: %s\n' "$CONFIG_PATH"
    print_log_info
    printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
    exit 0
fi

warn "当前状态: stale"
warn "原因：PID 不存在，或已不是当前仓库的 aitrade 进程。"
printf 'PID: %s\n' "$PID"
printf '项目目录: %s\n' "${REPO_ROOT:-$ROOT_DIR}"
printf '配置文件: %s\n' "$CONFIG_PATH"
print_log_info
printf '建议操作: bash stop.sh\n'
