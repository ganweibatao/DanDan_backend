from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Game, GameResult
from .serializers import GameSerializer, GameResultSerializer

class GameViewSet(viewsets.ModelViewSet):
    """
    API端点，允许游戏查看或编辑
    """
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['course', 'game_type', 'difficulty_level', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'difficulty_level', 'created_at']

class GameResultViewSet(viewsets.ModelViewSet):
    """
    API端点，允许游戏结果查看或编辑
    """
    queryset = GameResult.objects.all()
    serializer_class = GameResultSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'game']
    ordering_fields = ['score', 'time_spent', 'created_at']
    
    def get_queryset(self):
        """按当前用户过滤游戏结果"""
        if not self.request.user.is_staff:
            return GameResult.objects.filter(user=self.request.user)
        return GameResult.objects.all() 