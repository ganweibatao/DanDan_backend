# 邮箱验证码功能实现说明

## 功能概述

邮箱验证码功能用于用户注册、找回密码、邮箱变更等场景的安全验证，通过腾讯云SES服务发送邮件，支持异步发送和限流控制。

## 技术实现

- **后端框架**：Django + Django REST Framework
- **邮件服务**：腾讯云SES（Simple Email Service）
- **异步处理**：Python标准库 ThreadPoolExecutor
- **数据存储**：PostgreSQL (Django ORM)
- **限流控制**：Django Cache

## 目录结构

```
back_web/
  ├── utils/
  │   └── email_service.py          # 邮件服务工具类
  ├── apps/
  │   └── accounts/
  │       ├── models.py             # 包含EmailVerificationCode模型
  │       ├── serializers.py        # 邮箱相关序列化器
  │       ├── views.py              # API视图函数
  │       └── urls.py               # API路由
  ├── templates/
  │   └── email_template.json       # 邮件模板设计文档
  └── englishlearning/
      └── settings.py               # 包含邮件服务配置
```

## API接口

### 1. 发送验证码

- **URL**: `/api/accounts/email/send-code/`
- **方法**: POST
- **权限**: 无需登录
- **请求参数**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **成功响应** (200 OK):
  ```json
  {
    "success": true,
    "message": "验证码已发送，有效期5分钟"
  }
  ```
- **失败响应**:
  - 400 Bad Request: 无效的邮箱地址
  - 429 Too Many Requests: 发送过于频繁
  - 500 Internal Server Error: 服务器错误

### 2. 验证验证码

- **URL**: `/api/accounts/email/verify-code/`
- **方法**: POST
- **权限**: 无需登录
- **请求参数**:
  ```json
  {
    "email": "user@example.com",
    "code": "123456"
  }
  ```
- **成功响应** (200 OK):
  ```json
  {
    "success": true,
    "message": "验证通过"
  }
  ```
- **失败响应**:
  - 400 Bad Request: 验证码无效或已过期
  - 500 Internal Server Error: 服务器错误

## 验证码规则

- 验证码为6位数字
- 有效期5分钟
- 同一邮箱60秒内只能请求一次验证码
- 验证码一次性使用，验证通过后标记为已使用

## 邮件模板

腾讯云SES支持邮件模板功能，在`templates/email_template.json`中提供了模板设计，包括HTML和纯文本两种格式。需要在腾讯云SES控制台创建后获取模板ID配置到`settings.py`中。

## 安全考虑

1. **限流控制**：防止恶意用户频繁请求验证码
2. **验证码有效期**：减少暴力破解风险
3. **一次性使用**：防止重放攻击
4. **异步发送**：提高API响应速度，减少DOS攻击风险
5. **日志记录**：记录关键操作，便于问题追踪

## 扩展能力

1. 支持修改验证码位数、有效期等参数（通过settings.py配置）
2. 可扩展为支持短信验证码（需要添加短信服务提供商SDK）
3. 可扩展为支持语音验证码
4. 可调整限流策略，如基于IP的限流

## 使用流程示例

### 前端调用示例（注册场景）

```javascript
// 第一步：用户输入邮箱，请求验证码
async function requestEmailCode(email) {
  const response = await fetch('/api/accounts/email/send-code/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });
  const result = await response.json();
  return result;
}

// 第二步：用户输入验证码，进行验证
async function verifyEmailCode(email, code) {
  const response = await fetch('/api/accounts/email/verify-code/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, code })
  });
  const result = await response.json();
  return result;
}

// 第三步：验证通过后，提交注册信息
async function register(email, password, userType, code) {
  // 先验证验证码
  const verifyResult = await verifyEmailCode(email, code);
  if (!verifyResult.success) {
    return { error: verifyResult.error };
  }
  
  // 验证通过，执行注册
  const response = await fetch('/api/accounts/users/register/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, user_type: userType })
  });
  const result = await response.json();
  return result;
}
```

## 配置说明

在`settings.py`中包含以下配置项：

```python
# 腾讯云邮件发送服务配置
TENCENT_CLOUD_SECRET_ID = "您的SecretId"  # 从腾讯云控制台获取
TENCENT_CLOUD_SECRET_KEY = "您的SecretKey"  # 从腾讯云控制台获取
TENCENT_CLOUD_REGION = "ap-guangzhou"  # 腾讯云区域
EMAIL_FROM = "noreply@yourdomain.com"  # 发件人邮箱
EMAIL_TEMPLATE_ID = 12345  # 腾讯云SES邮件模板ID

# 邮箱验证码相关配置
EMAIL_CODE_EXPIRE_MINUTES = 5  # 验证码有效期(分钟)
EMAIL_CODE_LENGTH = 6  # 验证码长度
EMAIL_SEND_INTERVAL = 60  # 同一邮箱发送间隔(秒)
```

## 部署与维护

1. 确保已安装腾讯云SDK：`pip install tencentcloud-sdk-python`
2. 在腾讯云控制台创建SES邮件模板，获取模板ID
3. 更新`settings.py`中的配置信息
4. 运行数据库迁移：`python manage.py makemigrations` 和 `python manage.py migrate`
5. 重启Django服务

## 故障排查

1. 邮件发送失败：检查腾讯云SES配置，查看Django日志
2. 验证码无法验证：检查数据库，确认验证码是否正确保存
3. 限流触发：检查缓存配置是否正常，可适当调整限流参数 