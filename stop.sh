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

(venv) [root@gaopan-node30 aitrade]# cat stop.sh
#!/bin/bash
# 停止AI交易机器人脚本

PID_FILE="aitrade.pid"
LOG_FILE="trade.log"

# 检查PID文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "❌ PID文件不存在: $PID_FILE"
    echo "   机器人可能未运行或PID文件已被删除"
    exit 1
fi

# 读取PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ps -p $PID > /dev/null 2>&1; then
    echo "🔄 正在停止AI交易机器人 (PID: $PID)..."

    # 优雅地停止进程
    kill -TERM $PID

    # 等待进程结束
    TIMEOUT=30
    while [ $TIMEOUT -gt 0 ]; do
        if ! ps -p $PID > /dev/null 2>&1; then
            break
        fi
        sleep 1
        TIMEOUT=$((TIMEOUT - 1))
    done

    # 如果进程仍未停止，强制杀死
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  进程未响应，正在强制停止..."
        kill -KILL $PID
    fi

    # 删除PID文件
    rm -f "$PID_FILE"
    echo "✅ AI交易机器人已停止"
else
    echo "⚠️  进程不存在 (PID: $PID)"
    echo "   可能进程已停止或PID文件内容已过期"
    rm -f "$PID_FILE"
fi

# 显示最后几行日志
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "📋 最近日志输出:"
    tail -10 "$LOG_FILE"
fi
