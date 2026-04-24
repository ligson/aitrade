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
ssh "$SSH_ALIAS" "set -euo pipefail; rm -rf '$REMOTE_SHARED_PUBLIC_DIR'; mv '$REMOTE_SHARED_PUBLIC_TMP_DIR' '$REMOTE_SHARED_PUBLIC_DIR'; ln -sfn '$REMOTE_RELEASE_DIR' '$REMOTE_CURRENT_LINK'; if command -v semanage >/dev/null 2>&1; then semanage fcontext -a -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?' 2>/dev/null || semanage fcontext -m -t httpd_sys_content_t '${REMOTE_SHARED_PUBLIC_DIR}(/.*)?'; fi; restorecon -RF '$REMOTE_SHARED_PUBLIC_DIR' >/dev/null 2>&1 || true"

log '在远端重启 Web 服务并执行校验'
ssh "$SSH_ALIAS" "set -euo pipefail; cd '$REMOTE_CURRENT_LINK/aitrade-be'; bash init-env.sh; bash stop-web.sh || true; bash start-web.sh; bash status-web.sh; test -f '$REMOTE_SHARED_PUBLIC_DIR/index.html'; curl -fsS 'http://127.0.0.1:18080/health' >/dev/null"

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
printf 'ssh %s "curl -fsS http://127.0.0.1:18080/health"\n' "$SSH_ALIAS"
