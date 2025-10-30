#!/bin/bash
# 源码打包脚本

# 创建临时目录结构
mkdir -p temp_package/aitrade

# 创建dist目录（如果不存在）
if [ ! -d "dist" ]; then
  mkdir dist
else
  rm -rf dist/*
fi

# 获取当前时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PACKAGE_NAME="dist/aitrade_source_${TIMESTAMP}.zip"

echo "🚀 开始打包源码到 dist 目录..."

cp -r aitrade temp_package/aitrade/
cp *.sh temp_package/aitrade/
cp requirements.txt temp_package/aitrade/
cp config.example.yaml temp_package/aitrade/
cp README.md temp_package/aitrade/ 2>/dev/null || echo "README.md not found"

# 创建源码包，排除不必要的文件
cd temp_package
zip -r "../${PACKAGE_NAME}" \
    aitrade \
    -x "*.pyc" \
    "*__pycache__*" \
    "*.git*" \
    "*venv*" \
    "*.log" \
    "aitrade/dist/*" \
    "aitrade/build/*" \
    "aitrade/*.egg-info*" \
    "aitrade/package.sh" \
    "aitrade/config.yaml"

cd ..
# 清理临时目录
rm -rf temp_package

# 获取文件大小
FILE_SIZE=$(stat -c%s "$PACKAGE_NAME" 2>/dev/null || stat -f%z "$PACKAGE_NAME" 2>/dev/null)

echo "✅ 源码包创建完成: $PACKAGE_NAME ($FILE_SIZE bytes)"
echo "📦 包内文件结构:"
unzip -l "$PACKAGE_NAME" | head -20
