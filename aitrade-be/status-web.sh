#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
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

latest_web_log() {
    local latest
    latest=$(ls -1t "$LOG_DIR"/*.log 2>/dev/null | grep -v '/trade_' | grep -v '/launcher\.log$' | head -n 1 || true)
    if [ -n "$latest" ]; then
        printf '%s\n' "$latest"
    fi
}

pid_command() {
    local pid="$1"
    ps -p "$pid" -o command= 2>/dev/null || true
}

process_is_web_runner() {
    local pid="$1"
    local cmdline

    cmdline=$(pid_command "$pid")
    [ -n "$cmdline" ] && [[ "$cmdline" == *"-m aitrade.web_runner"* ]]
}

normalize_dir_path() {
    local dir_path="$1"

    if [ -z "$dir_path" ] || [ ! -d "$dir_path" ]; then
        printf '%s\n' "$dir_path"
        return 0
    fi

    (cd "$dir_path" && pwd -P) 2>/dev/null || printf '%s\n' "$dir_path"
}

process_cwd() {
    local pid="$1"

    if [ -L "/proc/$pid/cwd" ]; then
        readlink "/proc/$pid/cwd" 2>/dev/null || true
        return 0
    fi

    if [ "$HAS_LSOF" -ne 1 ]; then
        return 0
    fi

    lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep '^n' | head -n 1 | cut -c2- || true
}

process_matches() {
    local pid="$1"
    local cmdline
    local process_root

    if ! ps -p "$pid" >/dev/null 2>&1; then
        return 1
    fi

    if ! process_is_web_runner "$pid"; then
        return 1
    fi

    process_root=$(normalize_dir_path "$(process_cwd "$pid")")
    if [ -n "$process_root" ] && [ "$process_root" != "$ROOT_DIR" ]; then
        return 1
    fi

    return 0
}

port_listener_pid() {
    local port="$1"

    if [ "$HAS_LSOF" -ne 1 ] || [ -z "$port" ]; then
        return 1
    fi

    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
}

write_runtime_files() {
    local pid="$1"
    local started_at="$2"

    mkdir -p "$RUNTIME_DIR"
    cat > "$RUNTIME_FILE" <<EOF
PID=$pid
STARTED_AT=$started_at
REPO_ROOT=$ROOT_DIR
PYTHON_BIN=$VENV_PYTHON
CONFIG_PATH=$ROOT_DIR/config.yaml
LOG_DIR=$LOG_DIR
LAUNCHER_LOG=$LOG_DIR/web-launcher.log
WEB_HOST=$WEB_HOST
WEB_PORT=$WEB_PORT
EOF
    printf '%s\n' "$pid" > "$PID_FILE"
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

print_log_info() {
    printf '日志目录: %s\n' "$LOG_DIR"
    if [ -n "$(latest_web_log)" ]; then
        printf '最新应用日志: %s\n' "$(latest_web_log)"
    fi
}

print_listener_info() {
    if [ -z "${WEB_PORT:-}" ]; then
        return 0
    fi

    local listener_pid
    listener_pid=$(port_listener_pid "$WEB_PORT" || true)
    if [ -z "$listener_pid" ]; then
        printf '监听端口: %s (当前无 LISTEN 进程)\n' "$WEB_PORT"
        return 0
    fi

    printf '监听端口: %s\n' "$WEB_PORT"
    printf '监听 PID: %s\n' "$listener_pid"

    local listener_cmd
    listener_cmd=$(pid_command "$listener_pid")
    if [ -n "$listener_cmd" ]; then
        printf '监听命令: %s\n' "$listener_cmd"
    fi

    if [ -n "${PID:-}" ] && [ "$listener_pid" != "$PID" ]; then
        warn "运行态 PID 与实际监听 PID 不一致，可能仍有旧版本进程占用端口。"
    fi
}

cd "$ROOT_DIR"

if [ ! -f "$PID_FILE" ] && [ ! -f "$RUNTIME_FILE" ]; then
    resolve_configured_endpoint || true
    ORPHAN_LISTENER_PID=''
    if [ -n "${WEB_PORT:-}" ]; then
        ORPHAN_LISTENER_PID=$(port_listener_pid "$WEB_PORT" || true)
    fi

    if [ -n "$ORPHAN_LISTENER_PID" ]; then
        if process_matches "$ORPHAN_LISTENER_PID"; then
            warn "检测到运行态文件缺失，已按监听端口自动重建 Web 运行态。"
            write_runtime_files "$ORPHAN_LISTENER_PID" "unknown"
            info "当前状态: running"
            printf 'PID: %s\n' "$ORPHAN_LISTENER_PID"
            printf '启动时间: unknown\n'
            printf '访问地址: http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"
            printf '项目目录: %s\n' "$ROOT_DIR"
            printf '配置文件: %s\n' "$ROOT_DIR/config.yaml"
            print_log_info
            print_listener_info
            printf '启动辅助日志: %s\n' "$LOG_DIR/web-launcher.log"
            exit 0
        fi

        warn "当前状态: stale"
        if process_is_web_runner "$ORPHAN_LISTENER_PID"; then
            warn "原因：当前端口仍被其他发布目录中的 Web 进程占用。"
        else
            warn "原因：运行态文件缺失，但目标端口仍有监听进程。"
        fi
        printf '项目目录: %s\n' "$ROOT_DIR"
        print_log_info
        printf '监听端口: %s\n' "$WEB_PORT"
        printf '监听 PID: %s\n' "$ORPHAN_LISTENER_PID"
        ORPHAN_CMD=$(pid_command "$ORPHAN_LISTENER_PID")
        if [ -n "$ORPHAN_CMD" ]; then
            printf '监听命令: %s\n' "$ORPHAN_CMD"
        fi
        printf '建议操作: bash stop-web.sh\n'
        exit 0
    fi

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
WEB_HOST=''
WEB_PORT=''
if ! load_runtime; then
    warn "当前状态: stale"
    warn "原因：Web 运行态文件缺失或损坏。"
    printf '项目目录: %s\n' "$ROOT_DIR"
    print_log_info
    print_listener_info
    printf '建议操作: bash stop-web.sh\n'
    exit 0
fi

if process_matches "$PID"; then
    info "当前状态: running"
    printf 'PID: %s\n' "$PID"
    printf '启动时间: %s\n' "$STARTED_AT"
    printf '访问地址: http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"
    printf '项目目录: %s\n' "${REPO_ROOT:-$ROOT_DIR}"
    printf '配置文件: %s\n' "$CONFIG_PATH"
    print_log_info
    print_listener_info
    printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
    exit 0
fi

warn "当前状态: stale"
warn "原因：PID 不存在，或已不是当前仓库的 Web 进程。"
printf 'PID: %s\n' "$PID"
printf '项目目录: %s\n' "${REPO_ROOT:-$ROOT_DIR}"
printf '配置文件: %s\n' "$CONFIG_PATH"
print_log_info
print_listener_info
printf '建议操作: bash stop-web.sh\n'
