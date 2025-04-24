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

# Create your views here.

class UserDurationLogListCreateView(generics.ListCreateAPIView):
    serializer_class = UserDurationLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserDurationLog.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def force_report_student_duration(request):
    user = request.user
    if not hasattr(user, 'teacher_profile'):
        return Response({'error': '无权限，仅限老师操作'}, status=403)
    student_id = request.data.get('student_id')
    duration = request.data.get('duration')
    client_start_time = request.data.get('client_start_time')
    client_end_time = request.data.get('client_end_time')
    if not student_id or not duration:
        return Response({'error': '参数不完整'}, status=400)
    try:
        student_obj = Student.objects.get(id=student_id)
        user_obj = student_obj.user
    except Student.DoesNotExist:
        return Response({'error': '学生不存在'}, status=404)
    log = UserDurationLog.objects.create(
        user=user_obj,
        type='learning',
        duration=duration,
        client_start_time=client_start_time,
        client_end_time=client_end_time,
    )
    return Response({'status': 'ok', 'log_id': log.id})
