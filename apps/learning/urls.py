from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserProgressViewSet, SessionViewSet, StudyRecordViewSet

router = DefaultRouter()
router.register('progress', UserProgressViewSet, basename='progress')
router.register('sessions', SessionViewSet, basename='session')
router.register('records', StudyRecordViewSet, basename='record')

urlpatterns = [
    # 添加自定义URL路径
]

# 添加路由器的URL
urlpatterns += router.urls 