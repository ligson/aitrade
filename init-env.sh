#!/bin/bash
yum install -y git make gcc zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel libffi-devel tar gzip wget xz-devel
curl https://pyenv.run | bash
pyenv install 3.14.0
pyenv local 3.14.0
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt

