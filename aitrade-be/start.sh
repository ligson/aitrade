#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_DIR="$ROOT_DIR/.aitrade"
PID_FILE="$RUNTIME_DIR/aitrade.pid"
RUNTIME_FILE="$RUNTIME_DIR/runtime.env"
LOG_DIR="$ROOT_DIR/logs"
LAUNCHER_LOG="$LOG_DIR/launcher.log"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
CONFIG_FILE="$ROOT_DIR/config.yaml"

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

cleanup_stale_runtime() {
    rm -f "$PID_FILE" "$RUNTIME_FILE"
}

print_recent_logs() {
    if [ -f "$LAUNCHER_LOG" ]; then
        printf '%s\n' '--- 启动辅助日志（最近 20 行） ---'
        tail -n 20 "$LAUNCHER_LOG"
    fi

    local app_log
    app_log=$(latest_app_log)
    if [ -n "$app_log" ] && [ -f "$app_log" ]; then
        printf '%s\n' '--- 应用日志（最近 20 行） ---'
        tail -n 20 "$app_log"
    fi
}

recent_startup_content() {
    if [ -f "$LAUNCHER_LOG" ]; then
        tail -n 400 "$LAUNCHER_LOG" 2>/dev/null || true
    fi
}

startup_failure_reason() {
    local reason_line

    if [ ! -f "$LAUNCHER_LOG" ]; then
        return 1
    fi

    if grep -q '配置校验失败' "$LAUNCHER_LOG"; then
        printf '%s\n' '配置文件校验失败，请检查上面的具体配置项提示'
        return 0
    fi

    if grep -q '程序启动失败' "$LAUNCHER_LOG"; then
        if grep -q 'Using SOCKS proxy\|socksio' "$LAUNCHER_LOG"; then
            printf '%s\n' '检测到 SOCKS 代理，但当前环境缺少 socksio 依赖；请安装 httpx[socks] 或改用 HTTP 代理'
            return 0
        fi

        reason_line=$(grep '程序启动失败' "$LAUNCHER_LOG" | tail -n 1 || true)
        if [ -n "$reason_line" ]; then
            printf '%s\n' "$reason_line"
        else
            printf '%s\n' '启动阶段出现异常，请检查下面的日志输出'
        fi
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
    Config("./config.yaml", mode='bot')
except ConfigValidationError as exc:
    print(f"CONFIG_ERROR::{exc}")
    raise SystemExit(1)
except Exception as exc:
    print(f"CONFIG_ERROR::读取配置时发生异常: {exc}")
    raise SystemExit(1)
else:
    print("CONFIG_OK")
PY
); then
        return 0
    fi

    error "配置文件校验失败。"
    if [[ "$output" == *"CONFIG_ERROR::"* ]]; then
        error "原因：${output##*CONFIG_ERROR::}"
    else
        error "原因：$output"
    fi
    error "建议：修正 config.yaml 后重新执行 bash start.sh"
    return 1
}

is_startup_successful() {
    if [ ! -f "$LAUNCHER_LOG" ]; then
        return 1
    fi

    if startup_failure_reason > /dev/null; then
        return 1
    fi

    grep -q '交易周期完成' "$LAUNCHER_LOG" || (
        grep -q '开始新的交易周期' "$LAUNCHER_LOG" &&
        grep -q '获取AI交易信号时发生错误' "$LAUNCHER_LOG"
    )
}

cd "$ROOT_DIR"

if [ ! -x "$VENV_PYTHON" ]; then
    error "未找到 uv 环境中的 Python：$VENV_PYTHON"
    error "原因：环境尚未初始化完成。"
    error "建议：先执行 bash init-env.sh"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    error "未找到配置文件：$CONFIG_FILE"
    error "原因：尚未生成配置文件，或文件被删除。"
    error "建议：先执行 bash init-env.sh，并补全 config.yaml 后再重试"
    exit 1
fi

mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

if ! validate_config; then
    exit 1
fi

if [ -f "$PID_FILE" ]; then
    EXISTING_PID=$(tr -d '[:space:]' < "$PID_FILE")
    if [ -n "$EXISTING_PID" ] && process_matches "$EXISTING_PID"; then
        info "服务已在运行。"
        printf 'PID: %s\n' "$EXISTING_PID"
        printf '项目目录: %s\n' "$ROOT_DIR"
        printf '配置文件: %s\n' "$CONFIG_FILE"
        printf '日志目录: %s\n' "$LOG_DIR"
        printf '查看状态: bash status.sh\n'
        printf '停止服务: bash stop.sh\n'
        exit 0
    fi

    warn "检测到陈旧运行态，已自动清理。"
    cleanup_stale_runtime
fi

: > "$LAUNCHER_LOG"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
nohup "$VENV_PYTHON" -m aitrade >> "$LAUNCHER_LOG" 2>&1 &
PID=$!

ATTEMPTS=20
while [ "$ATTEMPTS" -gt 0 ]; do
    if ! process_matches "$PID"; then
        break
    fi

    if is_startup_successful; then
        cat > "$RUNTIME_FILE" <<EOF
PID=$PID
STARTED_AT=$STARTED_AT
REPO_ROOT=$ROOT_DIR
PYTHON_BIN=$VENV_PYTHON
CONFIG_PATH=$CONFIG_FILE
LOG_DIR=$LOG_DIR
LAUNCHER_LOG=$LAUNCHER_LOG
EOF
        printf '%s\n' "$PID" > "$PID_FILE"

        ok "AI 交易服务已正常启动。"
        printf 'PID: %s\n' "$PID"
        printf '项目目录: %s\n' "$ROOT_DIR"
        printf '配置文件: %s\n' "$CONFIG_FILE"
        printf '日志目录: %s\n' "$LOG_DIR"
        if [ -n "$(latest_app_log)" ]; then
            printf '最新应用日志: %s\n' "$(latest_app_log)"
        fi
        if [ -n "$(latest_trade_log)" ]; then
            printf '最新交易日志: %s\n' "$(latest_trade_log)"
        fi
        printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
        printf '查看状态: bash status.sh\n'
        printf '停止服务: bash stop.sh\n'
        exit 0
    fi

    if failure_reason=$(startup_failure_reason); then
        kill_startup_process "$PID"
        cleanup_stale_runtime
        error "服务启动失败。"
        error "原因：$failure_reason"
        error "建议：根据下面的日志输出检查配置、网络、交易所连接或代码异常"
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
EOF
    printf '%s\n' "$PID" > "$PID_FILE"

    warn "服务进程仍在运行，但在检查窗口内未捕获成功标记。"
    warn "原因：日志写入可能存在延迟，或当前交易周期尚未完成。"
    printf 'PID: %s\n' "$PID"
    printf '项目目录: %s\n' "$ROOT_DIR"
    printf '配置文件: %s\n' "$CONFIG_FILE"
    printf '日志目录: %s\n' "$LOG_DIR"
    if [ -n "$(latest_app_log)" ]; then
        printf '最新应用日志: %s\n' "$(latest_app_log)"
    fi
    if [ -n "$(latest_trade_log)" ]; then
        printf '最新交易日志: %s\n' "$(latest_trade_log)"
    fi
    printf '启动辅助日志: %s\n' "$LAUNCHER_LOG"
    printf '查看状态: bash status.sh\n'
    printf '停止服务: bash stop.sh\n'
    exit 0
fi

cleanup_stale_runtime
error "服务启动失败。"
if ! ps -p "$PID" > /dev/null 2>&1; then
    error "原因：进程在启动阶段提前退出。"
else
    error "原因：进程仍在运行，但在检查窗口内未出现成功启动标记。"
fi
error "建议：根据下面的日志输出检查配置、网络、交易所连接或代码异常"
print_recent_logs
exit 1
