#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/aitrade-be"
TARGET_SCRIPT="$BACKEND_DIR/package.sh"

if [ ! -f "$TARGET_SCRIPT" ]; then
    printf '[ERROR] 未找到后端脚本: %s\n' "$TARGET_SCRIPT" >&2
    exit 1
fi

cd "$BACKEND_DIR"
bash "$TARGET_SCRIPT" "$@"
