aitrade
=================================
A simple trading system for AI

## 配置

    1. 复制config.example.yaml为config.yaml
    2. 根据文件注释修改内容

## 创建虚拟环境

```bash
curl https://pyenv.run | bash
yum install -y make gcc zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel libffi-devel tar gzip wget xz-devel
pyenv install 3.14.0

unzip -d aitrade.zip
cd aitrade
pyenv local 3.14.0
python3 -m venv venv

# 激活虚拟环境
# Windows系统
venv\Scripts\activate
# Linux/Mac系统
source venv/bin/activate

# 退出虚拟环境
# Windows系统
venv\Scripts\deactivate
# Linux/Mac系统
source venv/bin/deactivate
 ```

## Install

```bash
pip3 install -r requirements.txt
```

## 运行

```bash
python -m aitrade
```

