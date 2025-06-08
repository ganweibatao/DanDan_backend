# 单词学习阶段 API 文档

本文档描述了基于艾宾浩斯遗忘曲线的单词学习阶段系统API接口。

## 概述

新的学习系统基于单词的学习阶段（Stage）而不是学习单元（Unit）。每个单词有6个学习阶段：

- Stage 0: 新词（立即可学习）
- Stage 1: 第1轮复习（1天后）
- Stage 2: 第2轮复习（1天后）
- Stage 3: 第3轮复习（2天后）
- Stage 4: 第4轮复习（3天后）
- Stage 5: 最终复习（7天后）

## 数据模型

### WordLearningStage 模型

```python
class WordLearningStage(models.Model):
    learning_plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE)
    book_word = models.ForeignKey(BookWord, on_delete=models.CASCADE)
    current_stage = models.IntegerField(default=0)  # 0-5
    start_date = models.DateField()
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
```

## API 接口

### 1. 获取学习计划的单词阶段信息

**端点**: `GET /api/v1/learning/plans/{plan_id}/words_stages/`

**描述**: 获取指定学习计划中所有单词的学习阶段信息，格式与前端 DuolingoStudyPlan 组件兼容。

**响应格式**:
```json
[
    {
        "word": "hello",
        "translation": "你好",
        "pronunciation": "/həˈloʊ/",
        "startDate": "2024-02-03",
        "currentStage": 1,
        "stageHistory": [
            {
                "stage": 0,
                "completedAt": "2024-02-03"
            },
            {
                "stage": 1,
                "completedAt": "2024-02-04"
            }
        ]
    }
]
```

**权限**: 需要认证，只能访问自己的学习计划

### 2. 推进单词到下一阶段

**端点**: `POST /api/v1/learning/plans/{plan_id}/advance_word_stage/`

**描述**: 将指定单词推进到下一个学习阶段，更新复习时间。

**请求体**:
```json
{
    "book_word_id": 123
}
```

**响应格式**:
```json
{
    "success": true,
    "message": "单词 \"hello\" 已推进到阶段 2",
    "word_stage": {
        "id": 456,
        "learning_plan": 1,
        "book_word": {...},
        "current_stage": 2,
        "start_date": "2024-02-03",
        "last_reviewed_at": "2024-02-05T10:30:00Z",
        "next_review_date": "2024-02-06"
    }
}
```

**权限**: 需要认证，只能操作自己的学习计划

## 前端集成

### 更新后的数据流

1. **VocabularyPage**: 用户点击"加入学习计划"
2. **后端**: 创建 LearningPlan 并自动为所有单词创建 WordLearningStage 记录
3. **Students.tsx**: 调用 `getWordsWithStages(planId)` 获取单词阶段数据
4. **DuolingoStudyPlan**: 根据 words 数组自动计算各阶段的单词数量

### API 调用示例

```typescript
// 获取单词阶段数据
const response = await apiClient.get(`learning/plans/${planId}/words-stages/`);
const wordsWithStages = response.data;

// 推进单词阶段
const response = await apiClient.post(`learning/plans/${planId}/advance_word_stage/`, {
    book_word_id: wordId
});
```

## 数据库迁移

运行以下命令来创建和应用数据库迁移：

```bash
# 创建迁移文件
python manage.py makemigrations learning

# 应用迁移
python manage.py migrate learning

# 为现有学习计划创建单词阶段记录
python manage.py create_word_stages
```

## 管理命令

### create_word_stages

为现有的学习计划创建单词学习阶段记录。

```bash
# 为所有学习计划创建单词阶段记录
python manage.py create_word_stages

# 为特定学习计划创建
python manage.py create_word_stages --plan-id 1

# 强制重新创建（删除现有记录）
python manage.py create_word_stages --force
```

## 测试

使用提供的测试脚本验证API功能：

```bash
python test_word_stages_api.py
```

确保Django服务器正在运行且有有效的测试数据。

## 注意事项

1. 新的学习系统与旧的基于Unit的系统并存，但前端已切换到基于Stage的模式
2. 创建学习计划时会自动为所有词库单词创建Stage 0记录
3. 单词的复习时间根据艾宾浩斯遗忘曲线自动计算
4. 管理后台可以查看和管理单词学习阶段记录 