#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.aitrade"
PID_FILE="$RUNTIME_DIR/web.pid"
RUNTIME_FILE="$RUNTIME_DIR/web.runtime.env"
LOG_DIR="$ROOT_DIR/logs"
LAUNCHER_LOG="$LOG_DIR/web-launcher.log"
VENV_BIN_DIR="$ROOT_DIR/.venv/bin"
VENV_PYTHON="$VENV_BIN_DIR/python"
CONFIG_FILE="$ROOT_DIR/config.yaml"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="18080"

info() {
    printf '[INFO] %s\n' "$1"
}

ok() {
    printf '[OK] %s\n' "$1"
}

warn() {
    printf '[WARN] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

latest_web_log() {
    local latest
    latest=$(ls -1t "$LOG_DIR"/*.log 2>/dev/null | grep -v '/trade_' | grep -v '/launcher\.log$' | head -n 1 || true)
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

    [[ "$cmdline" == *"$VENV_PYTHON"* && "$cmdline" == *"-m aitrade.web_runner"* ]]
}

cleanup_stale_runtime() {
    rm -f "$PID_FILE" "$RUNTIME_FILE"
}

print_recent_logs() {
    if [ -f "$LAUNCHER_LOG" ]; then
        printf '%s\n' '--- Web 启动辅助日志（最近 20 行） ---'
        tail -n 20 "$LAUNCHER_LOG"
    fi

    local app_log
    app_log=$(latest_web_log)
    if [ -n "$app_log" ] && [ -f "$app_log" ]; then
        printf '%s\n' '--- Web 应用日志（最近 20 行） ---'
        tail -n 20 "$app_log"
    fi
}

startup_failure_reason() {
    local reason_line

    if [ ! -f "$LAUNCHER_LOG" ]; then
        return 1
    fi

    if grep -q 'Web 配置校验失败' "$LAUNCHER_LOG"; then
        reason_line=$(grep 'Web 配置校验失败' "$LAUNCHER_LOG" | tail -n 1 || true)
        printf '%s\n' "${reason_line:-Web 配置校验失败，请检查 config.yaml}"
        return 0
    fi

    if grep -q 'Web 服务启动失败' "$LAUNCHER_LOG"; then
        reason_line=$(grep 'Web 服务启动失败' "$LAUNCHER_LOG" | tail -n 1 || true)
        printf '%s\n' "${reason_line:-Web 服务启动失败，请检查日志}"
        return 0
    fi

    if grep -q 'ERROR:' "$LAUNCHER_LOG"; then
        reason_line=$(grep 'ERROR:' "$LAUNCHER_LOG" | tail -n 1 || true)
        printf '%s\n' "${reason_line:-Web 服务启动失败，请检查日志}"
        return 0
    fi

    return 1
}

kill_startup_process() {
    local pid="$1"

    if ! process_matches "$pid"; then
        return 0
    fi

    kill -TERM "$pid" 2>/dev/null || true

    local attempts=5
    while [ "$attempts" -gt 0 ]; do
        if ! process_matches "$pid"; then
            return 0
        fi
        sleep 1
        attempts=$((attempts - 1))
    done

    kill -KILL "$pid" 2>/dev/null || true
}

validate_config() {
    local output
    if output=$(cd "$ROOT_DIR" && "$VENV_PYTHON" - <<'PY' 2>&1
from aitrade.config.config_file import Config, ConfigValidationError

try:
    cfg = Config('./config.yaml', mode='web')
    print(f"CONFIG_OK::{cfg.web_host}::{cfg.web_port}")
except ConfigValidationError as exc:
    print(f"CONFIG_ERROR::{exc}")
    raise SystemExit(1)
except Exception as exc:
    print(f"CONFIG_ERROR::读取配置时发生异常: {exc}")
    raise SystemExit(1)
PY
); then
        WEB_HOST=${output#CONFIG_OK::}
        WEB_HOST=${WEB_HOST%%::*}
        WEB_PORT=${output##*::}
        return 0
    fi

    error "Web 配置校验失败。"
    if [[ "$output" == *"CONFIG_ERROR::"* ]]; then
        error "原因：${output##*CONFIG_ERROR::}"
    else
        error "原因：$output"
    fi
    error "建议：修正 config.yaml 后重新执行 bash start-web.sh"
    return 1
}

health_check_ok() {
    local host="$1"
    local port="$2"
    "$VENV_PYTHON" - <<PY >/dev/null 2>&1
import sys
from urllib.request import urlopen

url = 'http://${host}:${port}/health'
try:
    with urlopen(url, timeout=2) as response:
        sys.exit(0 if 200 <= response.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
}

cd "$ROOT_DIR"

if [ ! -x "$VENV_PYTHON" ]; then
    error "未找到 uv 环境中的 Python：$VENV_PYTHON"
    error "建议：先执行 bash init-env.sh"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    error "未找到配置文件：$CONFIG_FILE"
    error "建议：先准备好 config.yaml 后再重试"
    exit 1
fi

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

export PATH="$VENV_BIN_DIR:$PATH"

WEB_HOST="$DEFAULT_HOST"
WEB_PORT="$DEFAULT_PORT"
if ! validate_config; then
    exit 1
fi

if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(tr -d '[:space:]' < "$PID_FILE")
    if [ -n "$EXISTING_PID" ] && process_matches "$EXISTING_PID"; then
        info "Web 服务已在运行。"
        printf 'PID: %s\n' "$EXISTING_PID"
        printf '访问地址: http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"
        printf '项目目录: %s\n' "$ROOT_DIR"
        printf '配置文件: %s\n' "$CONFIG_FILE"
        printf '日志目录: %s\n' "$LOG_DIR"
        printf '查看状态: bash status-web.sh\n'
        printf '停止服务: bash stop-web.sh\n'
        exit 0
    fi

    warn "检测到陈旧 Web 运行态，已自动清理。"
    cleanup_stale_runtime
fi

: > "$LAUNCHER_LOG"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
nohup "$VENV_PYTHON" -m aitrade.web_runner >> "$LAUNCHER_LOG" 2>&1 &
PID=$!

ATTEMPTS=20
while [ "$ATTEMPTS" -gt 0 ]; do
    if ! process_matches "$PID"; then
        break
    fi

    if health_check_ok "$WEB_HOST" "$WEB_PORT"; then
        cat > "$RUNTIME_FILE" <<EOF
PID=$PID
STARTED_AT=$STARTED_AT
REPO_ROOT=$ROOT_DIR
PYTHON_BIN=$VENV_PYTHON
CONFIG_PATH=$CONFIG_FILE
LOG_DIR=$LOG_DIR
LAUNCHER_LOG=$LAUNCHER_LOG
WEB_HOST=$WEB_HOST
WEB_PORT=$WEB_PORT
EOF
        printf '%s\n' "$PID" > "$PID_FILE"

        ok "Web 服务已正常启动。"
        printf 'PID: %s\n' "$PID"
        printf '访问地址: http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"
        printf '项目目录: %s\n' "$ROOT_DIR"
        printf '配置文件: %s\n' "$CONFIG_FILE"
        printf '日志目录: %s\n' "$LOG_DIR"
        if [ -n "$(latest_web_log)" ]; then
            printf '最新应用日志: %s\n' "$(latest_web_log)"
        fi
        printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
        printf '查看状态: bash status-web.sh\n'
        printf '停止服务: bash stop-web.sh\n'
        exit 0
    fi

    if failure_reason=$(startup_failure_reason); then
        kill_startup_process "$PID"
        cleanup_stale_runtime
        error "Web 服务启动失败。"
        error "原因：$failure_reason"
        print_recent_logs
        exit 1
    fi

    sleep 1
    ATTEMPTS=$((ATTEMPTS - 1))

done

if process_matches "$PID"; then
    cat > "$RUNTIME_FILE" <<EOF
PID=$PID
STARTED_AT=$STARTED_AT
REPO_ROOT=$ROOT_DIR
PYTHON_BIN=$VENV_PYTHON
CONFIG_PATH=$CONFIG_FILE
LOG_DIR=$LOG_DIR
LAUNCHER_LOG=$LAUNCHER_LOG
WEB_HOST=$WEB_HOST
WEB_PORT=$WEB_PORT
EOF
    printf '%s\n' "$PID" > "$PID_FILE"

    warn "Web 进程仍在运行，但在检查窗口内未通过健康检查。"
    printf 'PID: %s\n' "$PID"
    printf '访问地址: http://%s:%s\n' "$WEB_HOST" "$WEB_PORT"
    printf '项目目录: %s\n' "$ROOT_DIR"
    printf '配置文件: %s\n' "$CONFIG_FILE"
    printf '日志目录: %s\n' "$LOG_DIR"
    if [ -n "$(latest_web_log)" ]; then
        printf '最新应用日志: %s\n' "$(latest_web_log)"
    fi
    printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
    printf '查看状态: bash status-web.sh\n'
    printf '停止服务: bash stop-web.sh\n'
    exit 0
fi

cleanup_stale_runtime
error "Web 服务启动失败。"
print_recent_logs
exit 1
