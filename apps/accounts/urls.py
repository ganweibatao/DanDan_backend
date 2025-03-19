from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, TeacherViewSet, StudentViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('teachers', TeacherViewSet, basename='teacher')
router.register('students', StudentViewSet, basename='student')

urlpatterns = [
    # 添加自定义URL路径
]

# 添加路由器的URL
urlpatterns += router.urls 