#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"
PROJECT_NAME="aitrade-be"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
ARCHIVE_BASENAME="${PROJECT_NAME}_source_${TIMESTAMP}"
STAGING_DIR="$DIST_DIR/.${ARCHIVE_BASENAME}"
ARCHIVE_PATH="$DIST_DIR/${ARCHIVE_BASENAME}.tar.gz"

log() {
    printf '[package] %s\n' "$1"
}

error() {
    printf '[package][ERROR] %s\n' "$1" >&2
}

cleanup() {
    rm -rf "$STAGING_DIR"
}

resolve_tar_bin() {
    local os_name tar_version
    os_name="$(uname -s)"

    if [ "$os_name" != "Darwin" ]; then
        printf 'tar\n'
        return 0
    fi

    if command -v gtar >/dev/null 2>&1; then
        printf 'gtar\n'
        return 0
    fi

    tar_version="$(tar --version 2>/dev/null || true)"
    if printf '%s\n' "$tar_version" | grep -qi 'GNU tar'; then
        printf 'tar\n'
        return 0
    fi

    error '检测到当前系统是 macOS，但未找到 GNU tar。'
    error 'macOS 自带 bsdtar 生成的归档在 Linux 远端解压时会出现扩展头噪音，当前部署要求必须使用 GNU tar。'
    error '请先执行：brew install gnu-tar'
    error '安装后确认 `gtar --version` 可用，再重新执行 bash package.sh 或 bash deploy.sh'
    exit 1
}

trap cleanup EXIT

TAR_BIN="$(resolve_tar_bin)"

mkdir -p "$DIST_DIR"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/$PROJECT_NAME"

log "使用打包工具: $TAR_BIN"
log '开始准备源码包内容'
cp -R "$ROOT_DIR/aitrade" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR"/*.sh "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/pyproject.toml" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/uv.lock" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/config.example.yaml" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/README.md" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/CLAUDE.md" "$STAGING_DIR/$PROJECT_NAME/"

if [ -f "$ROOT_DIR/.python-version" ]; then
    cp "$ROOT_DIR/.python-version" "$STAGING_DIR/$PROJECT_NAME/"
fi

log '生成 tar.gz 压缩包'
"$TAR_BIN" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.log' \
    --exclude='.DS_Store' \
    --exclude='config.yaml' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='dist' \
    --exclude='.aitrade' \
    --exclude='aitrade.egg-info' \
    -czf "$ARCHIVE_PATH" \
    -C "$STAGING_DIR" \
    "$PROJECT_NAME"

FILE_SIZE=$(stat -f%z "$ARCHIVE_PATH" 2>/dev/null || stat -c%s "$ARCHIVE_PATH")

log "源码包创建完成: $ARCHIVE_PATH ($FILE_SIZE bytes)"
log '包内文件预览:'
set +o pipefail
"$TAR_BIN" -tzf "$ARCHIVE_PATH" | head -20
set -o pipefail
