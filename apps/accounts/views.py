from django.contrib.auth.models import User
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login
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
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """用户注册"""
        email = request.data.get('email')
        password = request.data.get('password')
        user_type = request.data.get('user_type')  # 'teacher' or 'student'
        
        # 验证必填字段
        if not email or not password or not user_type:
            return Response({
                'error': '请提供邮箱、密码和用户类型'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 验证邮箱是否已被注册
        if User.objects.filter(email=email).exists():
            return Response({
                'error': '该邮箱已被注册'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 使用邮箱作为用户名创建用户
        user = User.objects.create_user(
            username=email,  # 使用邮箱作为用户名
            email=email,
            password=password
        )
        
        # 创建用户profile
        if user_type == 'teacher':
            Teacher.objects.create(user=user)
        elif user_type == 'student':
            Student.objects.create(user=user)
        else:
            user.delete()
            return Response({
                'error': '无效的用户类型'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 创建token
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'user_id': user.id,
            'email': user.email,
            'user_type': user_type
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """用户登录"""
        email = request.data.get('email')  # 改为使用邮箱登录
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'error': '请提供邮箱和密码'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 使用邮箱作为用户名进行认证
        user = authenticate(username=email, password=password)
        
        if not user:
            return Response({
                'error': '邮箱或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
        login(request, user)
        token, _ = Token.objects.get_or_create(user=user)
        
        # 确定用户类型
        user_type = None
        if hasattr(user, 'teacher_profile'):
            user_type = 'teacher'
        elif hasattr(user, 'student_profile'):
            user_type = 'student'
            
        return Response({
            'token': token.key,
            'user_id': user.id,
            'email': user.email,
            'user_type': user_type
        })

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