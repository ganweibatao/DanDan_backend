from django.urls import path
from .views import (
    LearningPlanListCreateView, MarkUnitAsLearnedView, 
    MarkReviewAsCompletedView, TodayLearningView, AddNewWordsView,
    EbinghausMatrixDataView
)

urlpatterns = [
    # 学习计划API：获取或创建学习计划
    path('plans/', LearningPlanListCreateView.as_view(), name='learning-plans'),
    
    # 学习单元API：将特定学习单元标记为已学习
    path('units/<int:unit_id>/mark-learned/', MarkUnitAsLearnedView.as_view(), name='mark-unit-learned'),
    
    # 复习任务API：将特定复习任务标记为已完成
    path('reviews/<int:review_id>/mark-completed/', MarkReviewAsCompletedView.as_view(), name='mark-review-completed'),
    
    # 今日学习API：获取今天需要学习和复习的内容
    path('today/', TodayLearningView.as_view(), name='today-learning'),
    
    # 获取额外的新单词学习
    path('plan/<int:plan_id>/add_new_words/', AddNewWordsView.as_view(), name='add-new-words'),
    
    # 艾宾浩斯矩阵数据
    path('matrix-data/', EbinghausMatrixDataView.as_view(), name='matrix-data'),
] 