from django.shortcuts import render
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UserDurationLog
from .serializers import UserDurationLogSerializer
from django.db.models import Sum
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.accounts.models import Student
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncDate
# Import django-filter dependencies
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, DateFilter 

# Create your views here.

# Define a FilterSet for UserDurationLog
class UserDurationLogFilter(FilterSet):
    # Filter by exact date match on client_start_time's date part
    date = DateFilter(field_name='client_start_time__date', lookup_expr='exact', label='特定日期')
    # Allow filtering by student ID (maps to 'student' query param)
    student = CharFilter(field_name='student__id', lookup_expr='exact', label='学生ID') 
    # Allow filtering by type (e.g., ?type=teaching)
    type = CharFilter(field_name='type', lookup_expr='exact', label='日志类型')

    class Meta:
        model = UserDurationLog
        # Define fields available for filtering via query parameters
        fields = ['type', 'student', 'date'] 


class UserDurationLogListCreateView(generics.ListCreateAPIView):
    serializer_class = UserDurationLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    # Add DjangoFilterBackend and specify the FilterSet
    filter_backends = [DjangoFilterBackend]
    filterset_class = UserDurationLogFilter

    def get_queryset(self):
        """
        This view should return a list of all the duration logs
        for the currently authenticated user.
        Filtering by type, student, date is handled by DjangoFilterBackend.
        """
        # Only return logs for the requesting user
        return UserDurationLog.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Associate the log with the current user and potentially a student.
        """
        # Extract student_instance from validated data (provided by PrimaryKeyRelatedField)
        student_instance = serializer.validated_data.get('student', None) 
        # Save with the current user and the associated student instance
        serializer.save(user=self.request.user, student=student_instance) 

class UserDurationLogSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = UserDurationLog.objects.filter(user=request.user)
        summary = (
            qs.values('type')
            .annotate(total_duration=Sum('duration'))
            .order_by('type')
        )
        return Response({'summary': list(summary)})

class TeacherDailyTeachingDurationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # 确保是教师用户
        if not hasattr(user, 'teacher_profile'):
             return Response({'error': '无权限，仅限老师操作'}, status=status.HTTP_403_FORBIDDEN)

        thirty_days_ago = timezone.now().date() - timedelta(days=30)

        # 查询并聚合数据
        daily_durations = UserDurationLog.objects.filter(
            user=user,
            type='teaching',
            # student filter could be added here if needed for this specific view
            created_at__date__gte=thirty_days_ago
        ).annotate(
            date=TruncDate('created_at')  # 按日期分组
        ).values(
            'date'
        ).annotate(
            total_duration=Sum('duration') # 计算每天的总时长
        ).order_by('date') # 按日期排序

        # 格式化输出
        result = [{'date': item['date'].strftime('%Y-%m-%d'), 'duration': item['total_duration']} for item in daily_durations]

        return Response(result, status=status.HTTP_200_OK)
