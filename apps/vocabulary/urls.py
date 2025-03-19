from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import WordViewSet, CategoryViewSet, CourseViewSet

router = DefaultRouter()
router.register('words', WordViewSet, basename='word')
router.register('categories', CategoryViewSet, basename='category')
router.register('courses', CourseViewSet, basename='course')

urlpatterns = [
    # 添加自定义URL路径
]

# 添加路由器的URL
urlpatterns += router.urls 