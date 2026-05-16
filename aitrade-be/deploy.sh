#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/aitrade-fe"
FRONTEND_DIST_DIR="$FRONTEND_DIR/dist"
DIST_DIR="$ROOT_DIR/dist"
REMOTE_WEB_PORT="18080"
VERIFY_ROUTE_PATH="/api/system/trade-task/logs/page"
STARTUP_MAX_ATTEMPTS="12"
STARTUP_SLEEP_SECONDS="2"

SSH_ALIAS=''
MODE='all'
REMOTE_BASE_DIR='/data/aitrade'
FRONTEND_API_BASE_URL=''
MODE_SOURCE='default'
POSITIONAL=()

REMOTE_RELEASES_DIR=''
REMOTE_SHARED_DIR=''
REMOTE_SHARED_PUBLIC_DIR=''
REMOTE_SHARED_PUBLIC_TMP_DIR=''
REMOTE_CURRENT_LINK=''
ARCHIVE_PATH=''
ARCHIVE_NAME=''
RELEASE_NAME=''
REMOTE_RELEASE_DIR=''
REMOTE_BACKEND_DIR=''
REMOTE_ARCHIVE_PATH=''

log() {
    printf '[deploy] %s\n' "$1"
}

error() {
    printf '[deploy][ERROR] %s\n' "$1" >&2
}

usage() {
    cat <<'EOF'
用法：
  bash deploy.sh <ssh_alias> [frontend|backend|all] [remote_base_dir] [frontend_api_base_url]
  bash deploy.sh <ssh_alias> [--mode frontend|backend|all] [--remote-base-dir <path>] [--frontend-api-base-url <url>]

说明：
  - 默认 mode 为 all
  - 兼容旧用法：bash deploy.sh chenws-japan
  - 兼容旧位置参数：第二个参数仍可继续传 remote_base_dir
  - 推荐新用法：bash deploy.sh chenws-japan --mode backend
  - 后端部署前默认拒绝重启仍有活跃交易任务的 Web；如确认风险，可设置 AITRADE_DEPLOY_ALLOW_ACTIVE_TASKS=1 强制继续
EOF
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "未找到 $1 命令"
        exit 1
    fi
}

is_mode() {
    case "$1" in
        all|frontend|backend) return 0 ;;
        *) return 1 ;;
    esac
}

parse_args() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --mode)
                if [ "$#" -lt 2 ]; then
                    error '--mode 缺少取值'
                    usage
                    exit 1
                fi
                MODE="$2"
                MODE_SOURCE='flag'
                shift 2
                ;;
            --remote-base-dir)
                if [ "$#" -lt 2 ]; then
                    error '--remote-base-dir 缺少取值'
                    usage
                    exit 1
                fi
                REMOTE_BASE_DIR="$2"
                shift 2
                ;;
            --frontend-api-base-url)
                if [ "$#" -lt 2 ]; then
                    error '--frontend-api-base-url 缺少取值'
                    usage
                    exit 1
                fi
                FRONTEND_API_BASE_URL="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            --)
                shift
                while [ "$#" -gt 0 ]; do
                    POSITIONAL+=("$1")
                    shift
                done
                ;;
            -*)
                error "不支持的参数：$1"
                usage
                exit 1
                ;;
            *)
                POSITIONAL+=("$1")
                shift
                ;;
        esac
    done

    if [ "${#POSITIONAL[@]}" -lt 1 ]; then
        error '缺少 ssh_alias'
        usage
        exit 1
    fi

    SSH_ALIAS="${POSITIONAL[0]}"

    if [ "$MODE_SOURCE" = 'default' ] && [ "${#POSITIONAL[@]}" -ge 2 ] && is_mode "${POSITIONAL[1]}"; then
        MODE="${POSITIONAL[1]}"
        if [ "${#POSITIONAL[@]}" -ge 3 ]; then
            REMOTE_BASE_DIR="${POSITIONAL[2]}"
        fi
        if [ "${#POSITIONAL[@]}" -ge 4 ]; then
            FRONTEND_API_BASE_URL="${POSITIONAL[3]}"
        fi
        if [ "${#POSITIONAL[@]}" -gt 4 ]; then
            error '参数过多'
            usage
            exit 1
        fi
    else
        if [ "${#POSITIONAL[@]}" -ge 2 ]; then
            REMOTE_BASE_DIR="${POSITIONAL[1]}"
        fi
        if [ "${#POSITIONAL[@]}" -ge 3 ]; then
            FRONTEND_API_BASE_URL="${POSITIONAL[2]}"
        fi
        if [ "${#POSITIONAL[@]}" -gt 3 ]; then
            error '参数过多'
            usage
            exit 1
        fi
    fi

    if ! is_mode "$MODE"; then
        error "不支持的部署模式：${MODE}（仅支持 all、frontend、backend）"
        usage
        exit 1
    fi
}

init_remote_paths() {
    REMOTE_RELEASES_DIR="$REMOTE_BASE_DIR/releases"
    REMOTE_SHARED_DIR="$REMOTE_BASE_DIR/shared"
    REMOTE_SHARED_PUBLIC_DIR="$REMOTE_SHARED_DIR/public"
    REMOTE_SHARED_PUBLIC_TMP_DIR="$REMOTE_SHARED_DIR/public.__deploying__"
    REMOTE_CURRENT_LINK="$REMOTE_BASE_DIR/current"
}

build_frontend() {
    log '开始构建前端产物'
    if [ -n "$FRONTEND_API_BASE_URL" ]; then
        VITE_API_BASE_URL="$FRONTEND_API_BASE_URL" pnpm --dir "$FRONTEND_DIR" build
    else
        pnpm --dir "$FRONTEND_DIR" build
    fi

    if [ ! -d "$FRONTEND_DIST_DIR" ]; then
        error "前端构建目录不存在：$FRONTEND_DIST_DIR"
        exit 1
    fi
}

package_backend() {
    log '开始生成后端源码包'
    bash "$ROOT_DIR/package.sh"

    ARCHIVE_PATH=$(ls -1t "$DIST_DIR"/*.tar.gz 2>/dev/null | head -n 1 || true)
    if [ -z "$ARCHIVE_PATH" ]; then
        error '未找到后端源码包'
        exit 1
    fi

    ARCHIVE_NAME="$(basename "$ARCHIVE_PATH")"
    RELEASE_NAME="${ARCHIVE_NAME%.tar.gz}"
    REMOTE_RELEASE_DIR="$REMOTE_RELEASES_DIR/$RELEASE_NAME"
    REMOTE_BACKEND_DIR="$REMOTE_RELEASE_DIR/aitrade-be"
    REMOTE_ARCHIVE_PATH="$REMOTE_RELEASES_DIR/$ARCHIVE_NAME"
}

prepare_remote_dirs() {
    log "准备远端目录：$SSH_ALIAS:$REMOTE_BASE_DIR"
    ssh "$SSH_ALIAS" "mkdir -p '$REMOTE_RELEASES_DIR' '$REMOTE_SHARED_DIR'"
}

upload_backend_archive() {
    log "上传后端源码包：$ARCHIVE_NAME"
    scp "$ARCHIVE_PATH" "$SSH_ALIAS:$REMOTE_ARCHIVE_PATH"
}

prepare_backend_release_remote() {
    log '在远端解压后端源码包并准备共享配置'
    ssh "$SSH_ALIAS" "set -euo pipefail; rm -rf '$REMOTE_RELEASE_DIR'; mkdir -p '$REMOTE_RELEASE_DIR'; tar -xzf '$REMOTE_ARCHIVE_PATH' -C '$REMOTE_RELEASE_DIR'; if [ ! -f '$REMOTE_SHARED_DIR/config.yaml' ]; then cp '$REMOTE_BACKEND_DIR/config.example.yaml' '$REMOTE_SHARED_DIR/config.yaml'; fi; ln -sfn '$REMOTE_SHARED_DIR/config.yaml' '$REMOTE_BACKEND_DIR/config.yaml'"
}

upload_frontend_dist() {
    log '上传前端静态产物到共享目录'
    ssh "$SSH_ALIAS" "rm -rf '$REMOTE_SHARED_PUBLIC_TMP_DIR' && mkdir -p '$REMOTE_SHARED_PUBLIC_TMP_DIR'"
    scp -r "$FRONTEND_DIST_DIR/." "$SSH_ALIAS:$REMOTE_SHARED_PUBLIC_TMP_DIR/"
    ssh "$SSH_ALIAS" "set -euo pipefail; rm -rf '$REMOTE_SHARED_PUBLIC_DIR'; mv '$REMOTE_SHARED_PUBLIC_TMP_DIR' '$REMOTE_SHARED_PUBLIC_DIR'; if command -v semanage >/dev/null 2>&1; then semanage fcontext -a -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?' 2>/dev/null || semanage fcontext -m -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?'; fi; restorecon -RF '$REMOTE_SHARED_PUBLIC_DIR' >/dev/null 2>&1 || true"
}

guard_no_active_trade_tasks_remote() {
    log '检查远端是否存在活跃交易任务'
    ssh "$SSH_ALIAS" bash -s -- "$REMOTE_CURRENT_LINK" "${AITRADE_DEPLOY_ALLOW_ACTIVE_TASKS:-}" <<'EOF'
set -euo pipefail

REMOTE_CURRENT_LINK="$1"
ALLOW_ACTIVE_TASKS="${2:-}"
CURRENT_BACKEND_DIR="$REMOTE_CURRENT_LINK/aitrade-be"

if [ "$ALLOW_ACTIVE_TASKS" = '1' ]; then
    echo '[deploy][WARN] 已设置 AITRADE_DEPLOY_ALLOW_ACTIVE_TASKS=1，跳过活跃交易任务保护。'
    echo '[deploy][WARN] 如果当前有交易任务正在运行，本次重启可能中断任务线程并产生 stale 状态。'
    exit 0
fi

if [ ! -d "$CURRENT_BACKEND_DIR" ]; then
    echo '[deploy] 当前未发现可检查的 current Web 目录，跳过交易任务检查。'
    exit 0
fi

cd "$CURRENT_BACKEND_DIR"
PYTHON_BIN='.venv/bin/python'
if [ ! -x "$PYTHON_BIN" ]; then
    echo '[deploy][ERROR] 无法检查交易任务状态：当前后端虚拟环境不存在或不可执行。' >&2
    echo '[deploy][ERROR] 为避免中断可能正在运行的任务，本次部署中止。' >&2
    exit 3
fi

"$PYTHON_BIN" - <<'PY'
import sys

from sqlalchemy import inspect, text

from aitrade.config.config_file import Config
from aitrade.db.session import get_engine

active_statuses = ('starting', 'running', 'stop_requested')

try:
    config = Config('./config.yaml', mode='web')
    engine = get_engine(config.trade_persistence_config['database_url'])
    with engine.connect() as connection:
        if 'trade_task_runtime' not in inspect(connection).get_table_names():
            print('[deploy] 未发现交易任务运行态表，跳过交易任务检查。')
            sys.exit(0)
        rows = connection.execute(
            text(
                """
                SELECT runner_name, run_id, profile_name, symbol, timeframe, status, updated_at, next_run_at
                FROM trade_task_runtime
                WHERE status IN (:starting, :running, :stop_requested)
                ORDER BY runner_name ASC
                """
            ),
            {
                'starting': active_statuses[0],
                'running': active_statuses[1],
                'stop_requested': active_statuses[2],
            },
        ).mappings().all()
except Exception as exc:
    print(f'[deploy][ERROR] 无法确认交易任务状态：{exc}', file=sys.stderr)
    print('[deploy][ERROR] 为避免中断可能正在运行的任务，本次部署中止。', file=sys.stderr)
    sys.exit(3)

if not rows:
    print('[deploy] 未发现活跃交易任务，可以继续后端部署。')
    sys.exit(0)

print('[deploy][ERROR] 检测到活跃交易任务，已中止后端部署。', file=sys.stderr)
print('[deploy][ERROR] 请先在管理台停止任务，确认状态为 stopped 后再重新部署。', file=sys.stderr)
print('[deploy][ERROR] 如确认必须强制重启，可设置 AITRADE_DEPLOY_ALLOW_ACTIVE_TASKS=1。', file=sys.stderr)
for row in rows:
    print(
        '[deploy][ERROR] '
        f"runner={row['runner_name']} run_id={row['run_id'] or ''} "
        f"profile={row['profile_name'] or ''} symbol={row['symbol'] or ''} "
        f"timeframe={row['timeframe'] or ''} status={row['status']} "
        f"updated_at={row['updated_at'] or ''} next_run_at={row['next_run_at'] or ''}",
        file=sys.stderr,
    )
sys.exit(2)
PY
EOF
}

stop_current_backend() {
    log '在远端停止当前 Web 服务'
    ssh "$SSH_ALIAS" "set -euo pipefail; if [ -L '$REMOTE_CURRENT_LINK' ] && [ -d '$REMOTE_CURRENT_LINK/aitrade-be' ]; then cd '$REMOTE_CURRENT_LINK/aitrade-be'; bash stop-web.sh || true; else echo '[deploy] 当前未发现可停止的 current Web 目录'; fi"
}

restart_backend_remote() {
    log '切换 current 到新版本并重启 Web 服务'
    ssh "$SSH_ALIAS" "set -euo pipefail; ln -sfn '$REMOTE_RELEASE_DIR' '$REMOTE_CURRENT_LINK'; cd '$REMOTE_CURRENT_LINK/aitrade-be'; bash init-env.sh; bash start-web.sh; bash status-web.sh"
}

verify_frontend_remote() {
    log '校验远端前端静态目录'
    ssh "$SSH_ALIAS" "test -f '$REMOTE_SHARED_PUBLIC_DIR/index.html'"
}

verify_backend_remote() {
    log '执行远端后端部署校验'
    ssh "$SSH_ALIAS" bash -s -- "$REMOTE_CURRENT_LINK" "$REMOTE_RELEASE_DIR" "$REMOTE_WEB_PORT" "$VERIFY_ROUTE_PATH" "$STARTUP_MAX_ATTEMPTS" "$STARTUP_SLEEP_SECONDS" <<'EOF'
set -euo pipefail

REMOTE_CURRENT_LINK="$1"
REMOTE_RELEASE_DIR="$2"
REMOTE_WEB_PORT="$3"
VERIFY_ROUTE_PATH="$4"
STARTUP_MAX_ATTEMPTS="$5"
STARTUP_SLEEP_SECONDS="$6"
HEALTH_OUTPUT_FILE="/tmp/aitrade-health.out"
OPENAPI_OUTPUT_FILE="/tmp/aitrade-openapi.json"

CURRENT_TARGET="$(readlink "$REMOTE_CURRENT_LINK")"
if [ "$CURRENT_TARGET" != "$REMOTE_RELEASE_DIR" ]; then
    echo "[deploy][ERROR] current 软链未指向本次版本：$CURRENT_TARGET"
    exit 1
fi

ATTEMPT=1
LAST_STATUS_OUTPUT=''
LAST_HEALTH_CODE=''
LAST_HEALTH_BODY=''
LAST_OPENAPI_ERROR=''

# Web 进程启动到真正接管端口和路由表之间可能有短暂窗口，这里重试等待避免误报。
while [ "$ATTEMPT" -le "$STARTUP_MAX_ATTEMPTS" ]; do
    LAST_STATUS_OUTPUT="$(cd "$REMOTE_CURRENT_LINK/aitrade-be" && bash status-web.sh 2>&1 || true)"
    printf '[deploy] 启动校验第 %s/%s 次\n' "$ATTEMPT" "$STARTUP_MAX_ATTEMPTS"
    printf '%s\n' "$LAST_STATUS_OUTPUT"

    if printf '%s\n' "$LAST_STATUS_OUTPUT" | grep -q '\[INFO\] 当前状态: running'; then
        RUNTIME_PID="$(printf '%s\n' "$LAST_STATUS_OUTPUT" | grep '^PID:' | head -n 1 | awk '{print $2}')"
        LISTENER_PID="$(printf '%s\n' "$LAST_STATUS_OUTPUT" | grep '^监听 PID:' | head -n 1 | awk '{print $3}')"

        if [ -n "$LISTENER_PID" ] && [ "$RUNTIME_PID" = "$LISTENER_PID" ]; then
            LAST_HEALTH_CODE="$(curl -sS -o "$HEALTH_OUTPUT_FILE" -w '%{http_code}' "http://127.0.0.1:$REMOTE_WEB_PORT/health" || true)"
            LAST_HEALTH_BODY="$(cat "$HEALTH_OUTPUT_FILE" 2>/dev/null || true)"

            if [ "$LAST_HEALTH_CODE" -ge 200 ] && [ "$LAST_HEALTH_CODE" -lt 300 ]; then
                if curl -fsS "http://127.0.0.1:$REMOTE_WEB_PORT/openapi.json" -o "$OPENAPI_OUTPUT_FILE"; then
                    if python3 -c "import json,sys; data=json.load(open(sys.argv[1])); path=sys.argv[2]; sys.exit(0 if path in data.get('paths', {}) else 1)" "$OPENAPI_OUTPUT_FILE" "$VERIFY_ROUTE_PATH"; then
                        rm -f "$HEALTH_OUTPUT_FILE" "$OPENAPI_OUTPUT_FILE"
                        exit 0
                    fi
                    LAST_OPENAPI_ERROR="openapi.json 未包含关键路由 $VERIFY_ROUTE_PATH"
                else
                    LAST_OPENAPI_ERROR='openapi.json 拉取失败'
                fi
            fi
        fi
    fi

    if [ "$ATTEMPT" -lt "$STARTUP_MAX_ATTEMPTS" ]; then
        sleep "$STARTUP_SLEEP_SECONDS"
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

echo '[deploy][ERROR] Web 服务在等待窗口内仍未完成启动校验'
printf '%s\n' "$LAST_STATUS_OUTPUT"
if [ -n "$LAST_HEALTH_CODE" ]; then
    echo "[deploy][ERROR] 最近一次 /health 状态码：$LAST_HEALTH_CODE"
    if [ -n "$LAST_HEALTH_BODY" ]; then
        printf '%s\n' "$LAST_HEALTH_BODY"
    fi
fi
if [ -n "$LAST_OPENAPI_ERROR" ]; then
    echo "[deploy][ERROR] $LAST_OPENAPI_ERROR"
fi
if [ -f "$REMOTE_CURRENT_LINK/aitrade-be/logs/web-launcher.log" ]; then
    echo '[deploy][ERROR] 最近 60 行 web-launcher.log：'
    tail -n 60 "$REMOTE_CURRENT_LINK/aitrade-be/logs/web-launcher.log" || true
fi
exit 1
EOF
}

print_summary() {
    log '远端部署完成'
    printf '部署模式: %s\n' "$MODE"
    printf 'SSH 别名: %s\n' "$SSH_ALIAS"
    printf '远端根目录: %s\n' "$REMOTE_BASE_DIR"

    if [ "$MODE" = 'all' ] || [ "$MODE" = 'backend' ]; then
        printf '远端版本目录: %s\n' "$REMOTE_RELEASE_DIR"
        printf '后端目录: %s\n' "$REMOTE_BACKEND_DIR"
        printf '共享配置: %s/config.yaml\n' "$REMOTE_SHARED_DIR"
        printf 'current 软链: %s\n' "$REMOTE_CURRENT_LINK"
    fi

    if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
        printf '前端静态目录: %s\n' "$REMOTE_SHARED_PUBLIC_DIR"
    fi

    printf '\n部署后检查命令：\n'
    if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
        printf 'ssh %s "test -f %s/index.html && echo ok"\n' "$SSH_ALIAS" "$REMOTE_SHARED_PUBLIC_DIR"
    fi
    if [ "$MODE" = 'all' ] || [ "$MODE" = 'backend' ]; then
        printf 'ssh %s "cd %s && bash status-web.sh"\n' "$SSH_ALIAS" "$REMOTE_CURRENT_LINK/aitrade-be"
        printf 'ssh %s "curl -fsS http://127.0.0.1:%s/health"\n' "$SSH_ALIAS" "$REMOTE_WEB_PORT"
        printf 'ssh %s "curl -fsS http://127.0.0.1:%s/openapi.json | python3 -c '\''import json,sys; data=json.load(sys.stdin); print(sorted([p for p in data.get(\"paths\", {}) if p.startswith(\"/api/system/trade-task\")]))'\''"\n' "$SSH_ALIAS" "$REMOTE_WEB_PORT"
    fi
}

parse_args "$@"
init_remote_paths

require_cmd ssh
require_cmd scp

if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
    require_cmd pnpm
fi

log "部署参数: mode=$MODE ssh_alias=$SSH_ALIAS remote_base_dir=$REMOTE_BASE_DIR custom_frontend_api_base_url=$( [ -n "$FRONTEND_API_BASE_URL" ] && printf 'true' || printf 'false' )"

if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
    build_frontend
fi

if [ "$MODE" = 'all' ] || [ "$MODE" = 'backend' ]; then
    package_backend
fi

prepare_remote_dirs

if [ "$MODE" = 'all' ] || [ "$MODE" = 'backend' ]; then
    upload_backend_archive
    prepare_backend_release_remote
fi

if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
    upload_frontend_dist
fi

if [ "$MODE" = 'all' ] || [ "$MODE" = 'backend' ]; then
    guard_no_active_trade_tasks_remote
    stop_current_backend
    restart_backend_remote
    verify_backend_remote
fi

if [ "$MODE" = 'all' ] || [ "$MODE" = 'frontend' ]; then
    verify_frontend_remote
fi

print_summary
