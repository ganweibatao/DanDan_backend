from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import UserProgress, Session, StudyRecord
from .serializers import UserProgressSerializer, SessionSerializer, StudyRecordSerializer

class UserProgressViewSet(viewsets.ModelViewSet):
    """
    API端点，允许用户学习进度查看或编辑
    """
    queryset = UserProgress.objects.all()
    serializer_class = UserProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'course', 'current_level']
    ordering_fields = ['last_study_date', 'total_study_time', 'current_level']
    
    def get_queryset(self):
        """按当前用户过滤学习进度"""
        if not self.request.user.is_staff:
            return UserProgress.objects.filter(user=self.request.user)
        return UserProgress.objects.all()

class SessionViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学习会话查看或编辑
    """
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'course']
    ordering_fields = ['start_time', 'duration']
    
    def get_queryset(self):
        """按当前用户过滤学习会话"""
        if not self.request.user.is_staff:
            return Session.objects.filter(user=self.request.user)
        return Session.objects.all()

class StudyRecordViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学习记录查看或编辑
    """
    queryset = StudyRecord.objects.all()
    serializer_class = StudyRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'word', 'session', 'is_correct']
    ordering_fields = ['created_at', 'response_time']
    
    def get_queryset(self):
        """按当前用户过滤学习记录"""
        if not self.request.user.is_staff:
            return StudyRecord.objects.filter(user=self.request.user)
        return StudyRecord.objects.all() 