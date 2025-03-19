from django.contrib.auth.models import User
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Teacher, Student
from .serializers import UserSerializer, TeacherSerializer, StudentSerializer

class UserViewSet(viewsets.ModelViewSet):
    """
    API端点，允许用户查看或编辑
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """获取当前登录用户信息"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

class TeacherViewSet(viewsets.ModelViewSet):
    """
    API端点，允许教师信息查看或编辑
    """
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """可以按用户过滤教师"""
        queryset = Teacher.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset

class StudentViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学生信息查看或编辑
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """可以按用户过滤学生"""
        queryset = Student.objects.all()
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset 