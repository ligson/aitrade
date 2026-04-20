#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info() {
    printf '[INFO] %s\n' "$1"
}

error() {
    printf '[ERROR] %s\n' "$1" >&2
}

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    error "未检测到可用的 uv。"
    error "建议：先安装 uv，再执行 bash create-deps.sh"
    exit 1
fi

info "开始从 uv.lock 导出 requirements.txt。"
uv export --format requirements.txt --frozen --no-header --no-hashes --no-annotate --no-emit-project --output-file "$ROOT_DIR/requirements.txt"
info "requirements.txt 已更新。"
