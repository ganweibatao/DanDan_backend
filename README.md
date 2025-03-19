# 英语学习平台后端

这是一个基于Django和Django REST Framework构建的英语单词学习平台后端API服务。

## 技术栈

- **Django 5.1.7**: 核心框架
- **Django REST Framework 3.15.2**: RESTful API开发
- **SQLite/PostgreSQL**: 数据库存储
- **Django CORS Headers**: 处理跨域请求
- **Django Filters**: 提供高级过滤功能

## 项目结构

```
back_web/
├── englishlearning/              # 项目配置
│   ├── settings.py               # 全局设置
│   ├── urls.py                   # 全局URL配置
│   └── ...
├── apps/                         # 应用目录
│   ├── accounts/                 # 用户账户管理
│   │   ├── models.py             # 教师和学生模型
│   │   ├── serializers.py        # 序列化器
│   │   ├── views.py              # API视图
│   │   └── ...
│   ├── vocabulary/               # 词汇管理
│   │   ├── models.py             # 单词、分类、课程模型
│   │   ├── serializers.py        # 序列化器
│   │   ├── views.py              # API视图
│   │   └── ...
│   ├── learning/                 # 学习进度管理
│   │   ├── models.py             # 学习进度、会话、记录模型
│   │   ├── serializers.py        # 序列化器
│   │   ├── views.py              # API视图
│   │   └── ...
│   ├── games/                    # 学习游戏
│   │   ├── models.py             # 游戏和游戏结果模型
│   │   ├── serializers.py        # 序列化器
│   │   ├── views.py              # API视图
│   │   └── ...
│   └── analytics/                # 学习分析
│       ├── models.py             # 统计和报告模型
│       ├── serializers.py        # 序列化器
│       ├── views.py              # API视图
│       └── ...
├── venv/                         # Python虚拟环境
└── manage.py                     # Django管理脚本
```

## 数据模型

### 用户账户 (accounts)

- **Teacher**: 教师信息，包括职称、专长领域
- **Student**: 学生信息，包括英语水平、兴趣爱好、学习目标

### 词汇管理 (vocabulary)

- **Category**: 单词分类
- **Word**: 单词信息，包括拼写、发音、定义、例句
- **Course**: 课程信息，关联教师、单词和分类

### 学习管理 (learning)

- **UserProgress**: 用户学习进度，跟踪课程完成情况
- **Session**: 学习会话，记录每次学习的细节
- **StudyRecord**: 学习记录，包括每个单词的学习结果

### 游戏系统 (games)

- **Game**: 游戏定义，包括游戏类型、难度、关联单词
- **GameResult**: 游戏结果，记录用户得分和学习情况

### 学习分析 (analytics)

- **LearningStat**: 学习统计，按日期汇总学习数据
- **Report**: 学习报告，生成不同周期的学习总结

## API端点

所有API端点都在`/api/v1/`路径下，按功能分为以下几个组：

### 账户管理

- `api/v1/accounts/users/`: 用户管理
- `api/v1/accounts/teachers/`: 教师信息
- `api/v1/accounts/students/`: 学生信息

### 词汇管理

- `api/v1/vocabulary/categories/`: 单词分类
- `api/v1/vocabulary/words/`: 单词
- `api/v1/vocabulary/courses/`: 课程

### 学习管理

- `api/v1/learning/progress/`: 学习进度
- `api/v1/learning/sessions/`: 学习会话
- `api/v1/learning/records/`: 学习记录

### 游戏系统

- `api/v1/games/games/`: 游戏
- `api/v1/games/results/`: 游戏结果

### 学习分析

- `api/v1/analytics/stats/`: 学习统计
- `api/v1/analytics/reports/`: 学习报告

## 特性

- **完整的用户管理**：区分学生和教师角色
- **词汇管理**：支持单词、分类和课程管理
- **学习跟踪**：记录用户的学习进度和学习效果
- **游戏学习**：支持多种学习游戏模式
- **数据分析**：提供学习统计和报告功能
- **权限控制**：基于用户角色的访问控制
- **过滤和搜索**：支持各种查询参数进行数据筛选

## 安装和运行

1. 克隆仓库
2. 创建并激活虚拟环境
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
3. 安装依赖
   ```
   pip install django djangorestframework psycopg2-binary django-cors-headers Pillow django-filter coreapi
   ```
4. 应用数据库迁移
   ```
   python manage.py migrate
   ```
5. 创建超级用户
   ```
   python manage.py createsuperuser
   ```
6. 运行开发服务器
   ```
   cd back_web && source venv/bin/activate && python manage.py runserver 0.0.0.0:8000
   ```

## 管理员访问

管理员界面可以通过`/admin/`访问，使用创建的超级用户凭据登录。

## API文档

API文档可以通过`/docs/`访问(需要安装coreapi并取消urls.py中的注释)。

## 认证

系统目前使用Django REST Framework的基本会话认证。建议在生产环境中配置JWT或OAuth2认证。

## 跨域资源共享

已配置CORS以允许前端应用访问API。开发环境允许所有来源，生产环境需要配置特定来源。 