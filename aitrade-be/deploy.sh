#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
SSH_ALIAS="${1:-chenws-japan}"
REMOTE_BASE_DIR="${2:-/data/aitrade}"
FRONTEND_API_BASE_URL="${3:-}"
FRONTEND_DIR="$REPO_ROOT/aitrade-fe"
FRONTEND_DIST_DIR="$FRONTEND_DIR/dist"
DIST_DIR="$ROOT_DIR/dist"
REMOTE_WEB_PORT="18080"
VERIFY_ROUTE_PATH="/api/system/trade-task/logs/page"
STARTUP_MAX_ATTEMPTS="12"
STARTUP_SLEEP_SECONDS="2"

log() {
    printf '[deploy] %s\n' "$1"
}

error() {
    printf '[deploy][ERROR] %s\n' "$1" >&2
}

if ! command -v ssh >/dev/null 2>&1; then
    error '未找到 ssh 命令'
    exit 1
fi

if ! command -v scp >/dev/null 2>&1; then
    error '未找到 scp 命令'
    exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
    error '未找到 pnpm 命令'
    exit 1
fi

cd "$ROOT_DIR"

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

log '开始生成后端源码包'
bash "$ROOT_DIR/package.sh"

ARCHIVE_PATH=$(ls -1t "$DIST_DIR"/*.tar.gz 2>/dev/null | head -n 1 || true)
if [ -z "$ARCHIVE_PATH" ]; then
    error '未找到后端源码包'
    exit 1
fi

ARCHIVE_NAME="$(basename "$ARCHIVE_PATH")"
RELEASE_NAME="${ARCHIVE_NAME%.tar.gz}"
REMOTE_RELEASES_DIR="$REMOTE_BASE_DIR/releases"
REMOTE_SHARED_DIR="$REMOTE_BASE_DIR/shared"
REMOTE_SHARED_PUBLIC_DIR="$REMOTE_SHARED_DIR/public"
REMOTE_SHARED_PUBLIC_TMP_DIR="$REMOTE_SHARED_DIR/public.__deploying__"
REMOTE_CURRENT_LINK="$REMOTE_BASE_DIR/current"
REMOTE_RELEASE_DIR="$REMOTE_RELEASES_DIR/$RELEASE_NAME"
REMOTE_BACKEND_DIR="$REMOTE_RELEASE_DIR/aitrade-be"
REMOTE_ARCHIVE_PATH="$REMOTE_RELEASES_DIR/$ARCHIVE_NAME"

log "准备远端目录：$SSH_ALIAS:$REMOTE_BASE_DIR"
ssh "$SSH_ALIAS" "mkdir -p '$REMOTE_RELEASES_DIR' '$REMOTE_SHARED_DIR'"

log "上传后端源码包：$ARCHIVE_NAME"
scp "$ARCHIVE_PATH" "$SSH_ALIAS:$REMOTE_ARCHIVE_PATH"

log '在远端解压后端源码包并准备共享配置'
ssh "$SSH_ALIAS" "set -euo pipefail; rm -rf '$REMOTE_RELEASE_DIR'; mkdir -p '$REMOTE_RELEASE_DIR'; tar -xzf '$REMOTE_ARCHIVE_PATH' -C '$REMOTE_RELEASE_DIR'; if [ ! -f '$REMOTE_SHARED_DIR/config.yaml' ]; then cp '$REMOTE_BACKEND_DIR/config.example.yaml' '$REMOTE_SHARED_DIR/config.yaml'; fi; ln -sfn '$REMOTE_SHARED_DIR/config.yaml' '$REMOTE_BACKEND_DIR/config.yaml'"

log '上传前端静态产物到共享目录'
ssh "$SSH_ALIAS" "rm -rf '$REMOTE_SHARED_PUBLIC_TMP_DIR' && mkdir -p '$REMOTE_SHARED_PUBLIC_TMP_DIR'"
scp -r "$FRONTEND_DIST_DIR/." "$SSH_ALIAS:$REMOTE_SHARED_PUBLIC_TMP_DIR/"
ssh "$SSH_ALIAS" "set -euo pipefail; rm -rf '$REMOTE_SHARED_PUBLIC_DIR'; mv '$REMOTE_SHARED_PUBLIC_TMP_DIR' '$REMOTE_SHARED_PUBLIC_DIR'; if command -v semanage >/dev/null 2>&1; then semanage fcontext -a -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?' 2>/dev/null || semanage fcontext -m -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?'; fi; restorecon -RF '$REMOTE_SHARED_PUBLIC_DIR' >/dev/null 2>&1 || true"

log '在远端停止当前 Web 服务'
ssh "$SSH_ALIAS" "set -euo pipefail; if [ -L '$REMOTE_CURRENT_LINK' ] && [ -d '$REMOTE_CURRENT_LINK/aitrade-be' ]; then cd '$REMOTE_CURRENT_LINK/aitrade-be'; bash stop-web.sh || true; else echo '[deploy] 当前未发现可停止的 current Web 目录'; fi"

log '切换 current 到新版本并重启 Web 服务'
ssh "$SSH_ALIAS" "set -euo pipefail; ln -sfn '$REMOTE_RELEASE_DIR' '$REMOTE_CURRENT_LINK'; cd '$REMOTE_CURRENT_LINK/aitrade-be'; bash init-env.sh; bash start-web.sh; bash status-web.sh; test -f '$REMOTE_SHARED_PUBLIC_DIR/index.html'"

log '执行远端部署后校验'
ssh "$SSH_ALIAS" bash -s -- "$REMOTE_CURRENT_LINK" "$REMOTE_RELEASE_DIR" "$REMOTE_SHARED_PUBLIC_DIR" "$REMOTE_WEB_PORT" "$VERIFY_ROUTE_PATH" "$STARTUP_MAX_ATTEMPTS" "$STARTUP_SLEEP_SECONDS" <<'EOF'
set -euo pipefail

REMOTE_CURRENT_LINK="$1"
REMOTE_RELEASE_DIR="$2"
REMOTE_SHARED_PUBLIC_DIR="$3"
REMOTE_WEB_PORT="$4"
VERIFY_ROUTE_PATH="$5"
STARTUP_MAX_ATTEMPTS="$6"
STARTUP_SLEEP_SECONDS="$7"
HEALTH_OUTPUT_FILE="/tmp/aitrade-health.out"
OPENAPI_OUTPUT_FILE="/tmp/aitrade-openapi.json"

CURRENT_TARGET="$(readlink "$REMOTE_CURRENT_LINK")"
if [ "$CURRENT_TARGET" != "$REMOTE_RELEASE_DIR" ]; then
    echo "[deploy][ERROR] current 软链未指向本次版本：$CURRENT_TARGET"
    exit 1
fi

if [ ! -f "$REMOTE_SHARED_PUBLIC_DIR/index.html" ]; then
    echo "[deploy][ERROR] 前端静态文件缺失：$REMOTE_SHARED_PUBLIC_DIR/index.html"
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

echo "[deploy][ERROR] Web 服务在等待窗口内仍未完成启动校验"
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

log '远端部署完成'
printf 'SSH 别名: %s\n' "$SSH_ALIAS"
printf '远端版本目录: %s\n' "$REMOTE_RELEASE_DIR"
printf '后端目录: %s\n' "$REMOTE_BACKEND_DIR"
printf '前端静态目录: %s\n' "$REMOTE_SHARED_PUBLIC_DIR"
printf '共享配置: %s/config.yaml\n' "$REMOTE_SHARED_DIR"
printf 'current 软链: %s\n' "$REMOTE_CURRENT_LINK"
printf '\n部署后检查命令：\n'
printf 'ssh %s "cd %s && bash status-web.sh"\n' "$SSH_ALIAS" "$REMOTE_CURRENT_LINK/aitrade-be"
printf 'ssh %s "test -f %s/index.html && echo ok"\n' "$SSH_ALIAS" "$REMOTE_SHARED_PUBLIC_DIR"
printf 'ssh %s "curl -fsS http://127.0.0.1:%s/health"\n' "$SSH_ALIAS" "$REMOTE_WEB_PORT"
printf 'ssh %s "curl -fsS http://127.0.0.1:%s/openapi.json | python3 -c '\''import json,sys; data=json.load(sys.stdin); print(sorted([p for p in data.get(\"paths\", {}) if p.startswith(\"/api/system/trade-task\")]))'\''"\n' "$SSH_ALIAS" "$REMOTE_WEB_PORT"
