bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
# 允许最长请求处理时间(秒)
timeout = 120
# 优雅关闭超时
graceful_timeout = 120
# 日志
accesslog = "log/access.log"
errorlog = "log/gunicorn.log"
loglevel = "info"

# 生产环境请不要开启代码热重载(reload)
# reload = False 