#!/bin/bash
cd "$(dirname "$0")"  # 切换到脚本所在目录
source venv/bin/activate

# 确保log目录存在
mkdir -p log

# 安装Gunicorn(如果尚未安装)
pip install gunicorn

# 使用Gunicorn启动Django应用，使用多个工作进程，添加--reload参数实现代码变更自动重启
# 添加--capture-output参数将标准输出和错误重定向到访问日志中
# 添加--access-logfile参数指定访问日志文件
nohup gunicorn --bind 0.0.0.0:8000 --workers 4 --reload --capture-output --access-logfile=log/access.log englishlearning.wsgi:application > log/gunicorn.log 2>&1 &

echo "Gunicorn服务已在后台启动，进程ID: $!"
echo "查看Gunicorn启动日志请使用: tail -f log/gunicorn.log"
echo "查看访问日志请使用: tail -f log/access.log"
echo "查看Django应用日志请使用: tail -f log/django.log"
echo "已启用自动重启功能，代码修改后服务会自动重新加载"