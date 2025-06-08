#!/bin/bash
echo "正在寻找Gunicorn进程..."
# 查找运行中的gunicorn进程
GUNICORN_PID=$(pgrep -f "gunicorn.*englishlearning.wsgi")

if [ -n "$GUNICORN_PID" ]; then
    echo "找到Gunicorn进程，PID: $GUNICORN_PID"
    echo "正在停止Gunicorn服务..."
    kill -15 $GUNICORN_PID
    sleep 2
    
    # 检查进程是否已经停止
    if pgrep -f "gunicorn.*englishlearning.wsgi" > /dev/null; then
        echo "尝试强制终止进程..."
        kill -9 $GUNICORN_PID
    fi
    
    echo "Gunicorn服务已停止"
else
    echo "未找到运行中的Gunicorn进程"
fi 