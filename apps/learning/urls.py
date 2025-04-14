from django.urls import path
from . import views

urlpatterns = [
    # 学习计划API：获取或创建学习计划
    path('plans/', views.LearningPlanListCreateView.as_view(), name='learning-plan-list'),
    
    # 学习单元API：将特定学习单元标记为已学习
    path('units/<int:unit_id>/mark-learned/', views.MarkUnitAsLearnedView.as_view(), name='mark-unit-learned'),
    
    # 复习任务API：将特定复习任务标记为已完成
    path('reviews/<int:review_id>/mark-completed/', views.MarkReviewAsCompletedView.as_view(), name='mark-review-completed'),
    
    # 今日学习API：获取今天需要学习和复习的内容
    path('today/', views.TodayLearningView.as_view(), name='today-learning'),
    
    # 获取计划中指定范围的单词
    path('plan-words/', views.PlanWordsRangeView.as_view(), name='plan-words-range'),
] 