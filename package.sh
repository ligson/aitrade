#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$ROOT_DIR/dist"
PROJECT_NAME="aitrade"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
ARCHIVE_BASENAME="${PROJECT_NAME}_source_${TIMESTAMP}"
STAGING_DIR="$DIST_DIR/.${ARCHIVE_BASENAME}"
ARCHIVE_PATH="$DIST_DIR/${ARCHIVE_BASENAME}.tar.gz"

log() {
    printf '[package] %s\n' "$1"
}

cleanup() {
    rm -rf "$STAGING_DIR"
}

trap cleanup EXIT

mkdir -p "$DIST_DIR"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR/$PROJECT_NAME"

log "开始准备源码包内容"
cp -R "$ROOT_DIR/aitrade" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR"/*.sh "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/requirements.txt" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/config.example.yaml" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/README.md" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/CHANGELOG.md" "$STAGING_DIR/$PROJECT_NAME/"
cp "$ROOT_DIR/CLAUDE.md" "$STAGING_DIR/$PROJECT_NAME/"

if [ -f "$ROOT_DIR/.python-version" ]; then
    cp "$ROOT_DIR/.python-version" "$STAGING_DIR/$PROJECT_NAME/"
fi

log "生成 tar.gz 压缩包"
tar \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.log' \
    --exclude='config.yaml' \
    --exclude='venv' \
    --exclude='dist' \
    -czf "$ARCHIVE_PATH" \
    -C "$STAGING_DIR" \
    "$PROJECT_NAME"

FILE_SIZE=$(stat -f%z "$ARCHIVE_PATH" 2>/dev/null || stat -c%s "$ARCHIVE_PATH")

log "源码包创建完成: $ARCHIVE_PATH ($FILE_SIZE bytes)"
log "包内文件预览:"
tar -tzf "$ARCHIVE_PATH" | head -20
