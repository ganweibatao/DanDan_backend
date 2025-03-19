from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import GameViewSet, GameResultViewSet

router = DefaultRouter()
router.register('games', GameViewSet, basename='game')
router.register('results', GameResultViewSet, basename='game-result')

urlpatterns = [
    # 添加自定义URL路径
]

# 添加路由器的URL
urlpatterns += router.urls 