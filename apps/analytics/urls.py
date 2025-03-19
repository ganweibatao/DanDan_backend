from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import LearningStatViewSet, ReportViewSet

router = DefaultRouter()
router.register('stats', LearningStatViewSet, basename='stat')
router.register('reports', ReportViewSet, basename='report')

urlpatterns = [
    # 添加自定义URL路径
]

# 添加路由器的URL
urlpatterns += router.urls 