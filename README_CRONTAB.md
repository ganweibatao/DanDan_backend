# 验证码定期清理功能

本项目使用`django-crontab`实现验证码数据的定期清理，防止数据库中验证码记录过多。

## 功能说明

- 每天凌晨3点自动运行清理任务
- 清理内容包括：所有已使用的验证码和所有已过期的验证码
- 清理日志记录在`/tmp/verification_cleanup.log`中

## 安装配置

1. 安装django-crontab：

```bash
pip install django-crontab
```

2. 确认`settings.py`中已添加相关配置：

```python
INSTALLED_APPS = [
    # ...
    'django_crontab',
    # ...
]

CRONJOBS = [
    # 每天凌晨3点执行验证码清理任务
    ('0 3 * * *', 'utils.cleanup_tasks.cleanup_verification_codes', '>> /tmp/verification_cleanup.log 2>&1'),
]
```

## 管理命令

### 添加定时任务

将项目中定义的所有crontab任务添加到系统的crontab中：

```bash
python manage.py crontab add
```

### 查看当前已添加的任务

```bash
python manage.py crontab show
```

### 移除所有任务

```bash
python manage.py crontab remove
```

### 重新启动所有任务（先移除再添加）

```bash
python manage.py crontab remove
python manage.py crontab add
```

## 注意事项

1. 任务运行需要cron服务在服务器上运行。如果使用的是Ubuntu，通常cron服务已安装并运行。

2. 使用`sudo service cron status`检查cron服务是否正常运行：
   ```bash
   sudo service cron status
   ```

3. 如果cron服务未运行，使用以下命令启动：
   ```bash
   sudo service cron start
   ```

4. 确保Django项目目录对执行cron任务的用户有权限访问。

5. 任务日志路径`/tmp/verification_cleanup.log`需要有写入权限。

## 手动执行

如需手动执行清理任务（无需等待cron调度），可以使用Django shell：

```bash
python manage.py shell -c "from utils.cleanup_tasks import cleanup_verification_codes; print(f'已清理{cleanup_verification_codes()}条记录')"
```

## 故障排查

如果任务未正常执行：

1. 检查cron日志以查看是否有错误：
   ```bash
   sudo grep CRON /var/log/syslog
   ```

2. 检查任务日志文件：
   ```bash
   cat /tmp/verification_cleanup.log
   ```

3. 确保`cleanup_tasks.py`中的导入路径正确且无语法错误。

4. 验证服务器时间是否正确设置（使用`date`命令）。 