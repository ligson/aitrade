#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
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

print_python_install_hint() {
    case "$(uname -s)" in
        Darwin)
            error "未检测到可用的 python3。"
            error "原因：当前系统未安装 Python 3，无法创建虚拟环境。"
            error "建议：先执行 brew install python@$PYTHON_VERSION_HINT，然后重新运行 bash init-env.sh"
            ;;
        Linux)
            error "未检测到可用的 python3。"
            error "原因：当前系统未安装 Python 3，无法创建虚拟环境。"
            error "建议：先用 apt-get、dnf 或 yum 安装 python3 和 python3-venv 后，再重新运行 bash init-env.sh"
            ;;
        *)
            error "未检测到可用的 python3。"
            error "原因：当前系统暂未提供自动安装提示。"
            error "建议：手动安装 Python 3 后重新运行 bash init-env.sh"
            ;;
    esac
}

cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    print_python_install_hint
    exit 1
fi

info "检测到 Python: $(command -v python3)"
info "开始创建或更新虚拟环境。"
python3 -m venv "$VENV_DIR"

info "开始安装 Python 依赖。"
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt"

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
printf '下一步: 先编辑 config.yaml，再执行 bash start.sh\n'
