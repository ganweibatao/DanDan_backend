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
        logs = UserDurationLog.objects.filter(
            user=user,
            type='teaching',
            created_at__date__gte=thirty_days_ago
        ).only('client_start_time', 'client_end_time', 'created_at')

        from collections import defaultdict
        day_to_intervals = defaultdict(list)
        for log in logs:
            start = log.client_start_time or log.created_at
            end = log.client_end_time or log.created_at
            day = start.date()
            day_to_intervals[day].append((start, end))

        def merge_intervals(intervals):
            if not intervals:
                return 0
            intervals.sort()
            total = 0
            prev_start, prev_end = intervals[0]
            for start, end in intervals[1:]:
                if start <= prev_end:
                    prev_end = max(prev_end, end)
                else:
                    total += (prev_end - prev_start).total_seconds()
                    prev_start, prev_end = start, end
            total += (prev_end - prev_start).total_seconds()
            return total

        result = []
        for day, intervals in day_to_intervals.items():
            total_seconds = merge_intervals(intervals)
            result.append({'date': day.strftime('%Y-%m-%d'), 'duration': int(total_seconds)})

        result.sort(key=lambda x: x['date'])
        return Response(result, status=status.HTTP_200_OK)

class StudentDailyLearningSummaryView(APIView):
    """返回指定学生近 N 日的学习时长与效率统计 (type='learning')"""
    permission_classes = [IsAuthenticated]

    DEFAULT_DAYS = 30

    def get(self, request, student_id):
        try:
            days = int(request.query_params.get('days', self.DEFAULT_DAYS))
        except ValueError:
            return Response({'error': 'days 参数必须为整数'}, status=status.HTTP_400_BAD_REQUEST)
        if days < 1 or days > 365:
            return Response({'error': 'days 参数需在 1-365 之间'}, status=status.HTTP_400_BAD_REQUEST)

        # 仅统计 type=learning 日志
        start_date = timezone.now().date() - timedelta(days=days - 1)

        qs = (
            UserDurationLog.objects
            .filter(student_id=student_id, type='learning', created_at__date__gte=start_date)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                duration=Sum('duration'),
                word_count=Sum('word_count'),
                wrong_word_count=Sum('wrong_word_count')
            )
            .order_by('day')
        )

        result = []
        for row in qs:
            wc = row['word_count'] or 0
            wrc = row['wrong_word_count'] or 0
            dur = row['duration'] or 0
            result.append({
                'date': row['day'].strftime('%Y-%m-%d'),
                'duration': int(dur),  # 秒
                'word_count': wc,
                'wrong_word_count': wrc,
                'avg_per_word': round(dur / 60 / wc, 2) if wc else None,
                'accuracy': round(100 - wrc * 100 / wc, 1) if wc else None,
            })

        return Response(result, status=status.HTTP_200_OK)
