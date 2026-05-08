#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.aitrade"
PID_FILE="$RUNTIME_DIR/web.pid"
RUNTIME_FILE="$RUNTIME_DIR/web.runtime.env"
LOG_DIR="$ROOT_DIR/logs"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
HAS_LSOF=0
if command -v lsof >/dev/null 2>&1; then
    HAS_LSOF=1
fi

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

pid_command() {
    local pid="$1"
    ps -p "$pid" -o command= 2>/dev/null || true
}

process_cwd() {
    local pid="$1"

    if [ "$HAS_LSOF" -ne 1 ]; then
        return 0
    fi

    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep '^n' | head -n 1 | cut -c2- || true
}

process_matches() {
    local pid="$1"
    local cmdline
    local process_root

    if ! ps -p "$pid" > /dev/null 2>&1; then
        return 1
    fi

    cmdline=$(pid_command "$pid")
    if [ -z "$cmdline" ]; then
        return 1
    fi
    if [[ "$cmdline" != *"-m aitrade.web_runner"* ]]; then
        return 1
    fi

    process_root=$(process_cwd "$pid")
    if [ -n "$process_root" ] && [ "$process_root" != "$ROOT_DIR" ]; then
        return 1
    fi

    return 0
}

cleanup_runtime() {
    rm -f "$PID_FILE" "$RUNTIME_FILE"
}

port_listener_pid() {
    local port="$1"

    if [ "$HAS_LSOF" -ne 1 ] || [ -z "$port" ]; then
        return 1
    fi

    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

resolve_configured_endpoint() {
    if [ -n "${WEB_PORT:-}" ] && [ -n "${WEB_HOST:-}" ]; then
        return 0
    fi

    if [ ! -x "$VENV_PYTHON" ] || [ ! -f "$ROOT_DIR/config.yaml" ]; then
        return 1
    fi

    local output
    if ! output=$(cd "$ROOT_DIR" && "$VENV_PYTHON" - <<'PY' 2>/dev/null
from aitrade.config.config_file import Config

cfg = Config('./config.yaml', mode='web')
print(f"WEB_ENDPOINT::{cfg.web_host}::{cfg.web_port}")
PY
); then
        return 1
    fi

    if [[ "$output" == WEB_ENDPOINT::*::* ]]; then
        WEB_HOST=${output#WEB_ENDPOINT::}
        WEB_HOST=${WEB_HOST%%::*}
        WEB_PORT=${output##*::}
        return 0
    fi

    return 1
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

PID=''
STARTED_AT=''
REPO_ROOT=''
PYTHON_BIN=''
CONFIG_PATH=''
LAUNCHER_LOG=''
WEB_HOST=''
WEB_PORT=''
if [ ! -f "$PID_FILE" ] && [ ! -f "$RUNTIME_FILE" ]; then
    resolve_configured_endpoint || true
    ORPHAN_LISTENER_PID=''
    if [ -n "${WEB_PORT:-}" ]; then
        ORPHAN_LISTENER_PID=$(port_listener_pid "$WEB_PORT" || true)
    fi

    if [ -n "$ORPHAN_LISTENER_PID" ] && process_matches "$ORPHAN_LISTENER_PID"; then
        warn "检测到运行态文件缺失，按监听端口停止当前 Web 进程。"
        PID="$ORPHAN_LISTENER_PID"
        STARTED_AT='unknown'
        REPO_ROOT="$ROOT_DIR"
        PYTHON_BIN="$VENV_PYTHON"
        CONFIG_PATH="$ROOT_DIR/config.yaml"
        LAUNCHER_LOG="$LOG_DIR/web-launcher.log"
    else
        info "Web 服务已停止，无需处理。"
        print_log_info
        exit 0
    fi
elif ! load_runtime; then
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
