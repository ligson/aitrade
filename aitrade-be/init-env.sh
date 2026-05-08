#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
CONFIG_TEMPLATE="$ROOT_DIR/config.example.yaml"
CONFIG_FILE="$ROOT_DIR/config.yaml"
PYTHON_VERSION_RAW="$(tr -d '[:space:]' < "$ROOT_DIR/.python-version" 2>/dev/null || true)"
PYTHON_VERSION_HINT="${PYTHON_VERSION_RAW:-3.14}"

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

print_uv_install_hint() {
    case "$(uname -s)" in
        Darwin)
            error "未检测到可用的 uv。"
            error "原因：当前系统未安装 uv，无法同步项目环境。"
            error "建议：先使用 Homebrew 或其他方式安装 uv，然后重新运行 bash init-env.sh"
            ;;
        Linux)
            error "未检测到可用的 uv。"
            error "原因：当前系统未安装 uv，无法同步项目环境。"
            error "建议：先使用系统包管理器或官方安装方式安装 uv，然后重新运行 bash init-env.sh"
            ;;
        *)
            error "未检测到可用的 uv。"
            error "原因：当前系统暂未提供自动安装提示。"
            error "建议：手动安装 uv 后重新运行 bash init-env.sh"
            ;;
    esac
}

cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
    print_uv_install_hint
    exit 1
fi

info "检测到 uv: $(command -v uv)"
info "开始创建或更新 uv 环境。"
uv sync --python "$PYTHON_VERSION_HINT" --locked

if [ ! -x "$VENV_PYTHON" ]; then
    error "未找到 uv 环境中的 Python：$VENV_PYTHON"
    error "原因：uv 环境同步未成功完成。"
    error "建议：检查上面的 uv 输出后重新执行 bash init-env.sh"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_TEMPLATE" "$CONFIG_FILE"
    ok "已根据模板生成 config.yaml。"
else
    info "检测到现有 config.yaml，保留原配置。"
fi

ok "环境初始化完成。"
printf '项目目录: %s\n' "$ROOT_DIR"
printf 'Python: %s\n' "$VENV_PYTHON"
printf '虚拟环境: %s\n' "$VENV_DIR"
printf '配置文件: %s\n' "$CONFIG_FILE"
printf '下一步: 先编辑 config.yaml，再执行 bash start-web.sh\n'
