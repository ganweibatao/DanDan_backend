from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import LearningStat, Report
from .serializers import LearningStatSerializer, ReportSerializer

class LearningStatViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学习统计查看或编辑
    """
    queryset = LearningStat.objects.all()
    serializer_class = LearningStatSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'course', 'date']
    ordering_fields = ['date', 'words_learned', 'correct_rate', 'study_time']
    
    def get_queryset(self):
        """按当前用户过滤学习统计"""
        if not self.request.user.is_staff:
            return LearningStat.objects.filter(user=self.request.user)
        return LearningStat.objects.all()

class ReportViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学习报告查看或编辑
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['user', 'report_type', 'course', 'start_date', 'end_date']
    ordering_fields = ['start_date', 'end_date', 'total_words', 'average_correct_rate', 'total_study_time']
    
    def get_queryset(self):
        """按当前用户过滤学习报告"""
        if not self.request.user.is_staff:
            return Report.objects.filter(user=self.request.user)
        return Report.objects.all() 