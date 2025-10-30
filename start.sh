#!/bin/bash
source venv/bin/activate

# 启动进程
nohup python -m aitrade >> trade.log 2>&1 &

# 保存PID
PID=$!
echo $PID > aitrade.pid

# 验证进程是否运行
if ps -p $PID > /dev/null; then
    echo "AI trade process started with PID: $PID"
else
    echo "Failed to start AI trade process"
fi
