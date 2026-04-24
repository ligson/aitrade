#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.aitrade"
PID_FILE="$RUNTIME_DIR/web.pid"
RUNTIME_FILE="$RUNTIME_DIR/web.runtime.env"
LOG_DIR="$ROOT_DIR/logs"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

info() {
    printf '[INFO] %s\n' "$1"
}

ok() {
    printf '[OK] %s\n' "$1"
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
                    PID|STARTED_AT|REPO_ROOT|PYTHON_BIN|CONFIG_PATH|LOG_DIR|LAUNCHER_LOG|WEB_HOST|WEB_PORT)
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

process_matches() {
    local pid="$1"
    local cmdline
    local expected_python="${PYTHON_BIN:-$VENV_PYTHON}"

    if ! ps -p "$pid" > /dev/null 2>&1; then
        return 1
    fi

    cmdline=$(ps -p "$pid" -o command= 2>/dev/null || true)
    if [ -z "$cmdline" ]; then
        return 1
    fi

    [[ "$cmdline" == *"$expected_python"* && "$cmdline" == *"-m aitrade.web_runner"* ]]
}

cleanup_runtime() {
    rm -f "$PID_FILE" "$RUNTIME_FILE"
}

latest_web_log() {
    local latest
    latest=$(ls -1t "$LOG_DIR"/*.log 2>/dev/null | grep -v '/trade_' | grep -v '/launcher\.log$' | head -n 1 || true)
    if [ -n "$latest" ]; then
        printf '%s\n' "$latest"
    fi
}

print_log_info() {
    printf '日志目录: %s\n' "$LOG_DIR"
    if [ -n "$(latest_web_log)" ]; then
        printf '最新应用日志: %s\n' "$(latest_web_log)"
    fi
}

cd "$ROOT_DIR"

if [ ! -f "$PID_FILE" ] && [ ! -f "$RUNTIME_FILE" ]; then
    info "Web 服务已停止，无需处理。"
    print_log_info
    exit 0
fi

PID=''
STARTED_AT=''
REPO_ROOT=''
PYTHON_BIN=''
CONFIG_PATH=''
LAUNCHER_LOG=''
WEB_HOST=''
WEB_PORT=''
if ! load_runtime; then
    warn "检测到损坏或不完整的 Web 运行态，已清理。"
    cleanup_runtime
    print_log_info
    exit 0
fi

if ! process_matches "$PID"; then
    warn "检测到陈旧 Web 运行态，已清理。"
    cleanup_runtime
    print_log_info
    exit 0
fi

info "正在停止 Web 服务，PID: $PID"
kill -TERM "$PID"

TIMEOUT=30
while [ "$TIMEOUT" -gt 0 ]; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        break
    fi
    sleep 1
    TIMEOUT=$((TIMEOUT - 1))
done

if ps -p "$PID" > /dev/null 2>&1; then
    warn "进程在宽限期内未退出，发送强制停止信号。"
    kill -KILL "$PID"
fi

cleanup_runtime
ok "Web 服务已停止。"
print_log_info
if [ -n "${LAUNCHER_LOG:-}" ]; then
    printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
fi
