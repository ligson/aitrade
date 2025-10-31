#!/bin/bash

PID_FILE="aitrade.pid"
LOG_FILE="trade.log"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "Service is not running (PID file not found)"
    exit 1
fi

# 读取PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ps -p $PID > /dev/null; then
    echo "Service is running with PID: $PID"
    
    # 显示最近的日志行
    if [ -f "$LOG_FILE" ]; then
        echo "Recent log entries:"
        tail -n 10 "$LOG_FILE"
    fi
    
    exit 0
else
    echo "Service is not running (process with PID $PID not found)"
    exit 1
fi