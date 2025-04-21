from django.contrib.auth.models import User
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Teacher, Student, StudentTeacherRelationship
from .serializers import UserSerializer, TeacherSerializer, StudentSerializer
from rest_framework.permissions import IsAuthenticated
from .permissions import IsTeacher, IsStudent, IsTeacherOrAdmin, IsTeacherOwnerOrAdmin, IsStudentOwnerOrRelatedTeacherOrAdmin

class UserViewSet(viewsets.ModelViewSet):
    """
    API端点，允许用户查看或编辑
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def current(self, request):
        """获取当前登录用户信息（包含角色）"""
        serializer = self.get_serializer(request.user)
        user_data = serializer.data

        # 确定用户类型
        user_type = None
        if hasattr(request.user, 'teacher_profile'):
            user_type = 'teacher'
            user_data['teacher_profile_id'] = request.user.teacher_profile.id
        elif hasattr(request.user, 'student_profile'):
            user_type = 'student'
            user_data['student_profile_id'] = request.user.student_profile.id
        elif request.user.is_staff:
            user_type = 'admin'

        user_data['user_type'] = user_type

        return Response(user_data)
    
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
            
        # 验证用户名(邮箱)是否已被注册
        if User.objects.filter(username=email).exists():
             return Response({
                 'error': '该用户名(邮箱)已被注册'
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
            # 注意：这里只创建了学生，没有关联老师，这部分逻辑移动到 TeacherViewSet.create_student
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
            
        login(request, user) # 这步会设置 session cookie，可以保留用于Django Admin等，但API认证主要靠下面的Token Cookie
        token, _ = Token.objects.get_or_create(user=user)
        
        # 确定用户类型
        user_type = None
        if hasattr(user, 'teacher_profile'):
            user_type = 'teacher'
        elif hasattr(user, 'student_profile'):
            user_type = 'student'
            
        # 创建响应对象
        response = Response({
            'user_id': user.id,
            'email': user.email,
            'user_type': user_type
        })

        # 设置 HttpOnly Cookie
        response.set_cookie(
            key='auth_token',  # Cookie 的名字
            value=token.key,   # Cookie 的值是 Token
            httponly=True,     # 关键：设置为 HttpOnly
            samesite='Lax',    # SameSite 策略，Lax 比较常用
            max_age=60*60*24*7, # <-- 设置过期时间为一周 (单位：秒)
            # secure=True,     # 在生产环境中 (HTTPS) 应设置为 True
            # expires=...     # 或者设置具体的过期日期时间
            path='/'           # Cookie 的有效路径
        )

        return response

    def get_permissions(self):
        """
        为不同的 action 设置不同的权限。
        对于 list, retrieve, update, partial_update, destroy 等标准 action，
        通常需要 IsAuthenticated 或 IsAdminUser。
        自定义 action (如 current, register, login) 已单独设置。
        """
        if self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
             # 假设只有管理员可以管理所有用户列表或修改/删除其他用户
             # 如果普通认证用户也需要某些权限（例如更新自己的信息），则需要更复杂的逻辑
             return [permissions.IsAdminUser()]
        # 对于 current, register, login，权限已在 @action 中定义
        # 如果有其他自定义 action，在此处添加它们的权限
        return super().get_permissions() # 回退到默认权限或空列表

class TeacherViewSet(viewsets.ModelViewSet):
    """
    API端点，允许教师信息查看或编辑
    """
    queryset = Teacher.objects.select_related('user').all() # Optimized queryset
    serializer_class = TeacherSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """可以按用户过滤教师"""
        # 优化点1: 使用select_related预加载关联的user数据，减少数据库查询次数
        queryset = Teacher.objects.select_related('user')
        
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        return queryset
        
    # @action(detail=True, methods=['get'], permission_classes=[]) # 测试无权限
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsTeacherOrAdmin])
    def students(self, request, pk=None):
        """获取指定教师的所有学生"""
        teacher = self.get_object()
        
        # 添加权限检查，确保只有当前教师或管理员可以查看此教师的学生
        if not request.user.is_staff and request.user.teacher_profile.id != teacher.id:
            return Response({"error": "没有权限查看其他教师的学生"}, status=status.HTTP_403_FORBIDDEN)
            
        students = teacher.students.all()
        page = self.paginate_queryset(students)
        if page is not None:
            serializer = StudentSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    # Use IsAuthenticated for list/retrieve, custom for others
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        # Allow teacher to update their own profile, or admin
        elif self.action in ['update', 'partial_update']:
             permission_classes = [IsAuthenticated, IsTeacherOwnerOrAdmin]
        # Restrict creation/deletion to admin? Or allow any authenticated user to become a teacher?
        # Assuming only admins can create/delete teacher profiles directly via this viewset
        elif self.action in ['create', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        # Custom actions need specific permissions
        elif self.action in ['create_student', 'remove_student']:
            permission_classes = [IsAuthenticated, IsTeacher]
        else:
            permission_classes = [IsAuthenticated] # Default
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsTeacher])
    @transaction.atomic # Ensure atomicity for user and student creation
    def create_student(self, request):
        """
        由登录的教师创建新学生并建立关联
        Expects: username, email, password, grade, [optional: age, gender, phone_number, personality_traits]
        """
        teacher = request.user.teacher_profile # Get teacher profile from logged-in user
        serializer = StudentSerializer(data=request.data, context={'request': request, 'teacher': teacher}) # Pass teacher to context

        # --- Data Validation ---
        email = request.data.get('email')
        username = request.data.get('username') # Frontend uses username
        password = request.data.get('password')
        grade = request.data.get('grade')

        if not email or not username or not password or not grade:
            return Response({'error': '缺少必填字段: 用户名, 邮箱, 密码, 年级'}, status=status.HTTP_400_BAD_REQUEST)

        # Check existing User (email or username)
        if User.objects.filter(email=email).exists():
            return Response({'error': f"邮箱 '{email}' 已被注册"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
             return Response({'error': f"用户名 '{username}' 已存在"}, status=status.HTTP_400_BAD_REQUEST)

        # --- Create User ---
        try:
            user = User.objects.create_user(
                username=username, # Use provided username
                email=email,
                password=password
            )
        except Exception as e:
             return Response({'error': f'创建用户失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Create Student Profile ---
        try:
            student_data = {
                'user': user,
                'grade': grade,
                'age': request.data.get('age'),
                'gender': request.data.get('gender'),
                'phone_number': request.data.get('phone_number'),
                'personality_traits': request.data.get('personality'),
            }
             # Filter out None values for optional fields before creation
            student_data_filtered = {k: v for k, v in student_data.items() if v is not None and v != ''}
            student = Student.objects.create(**student_data_filtered)

        except Exception as e:
            user.delete() # Rollback user creation
            return Response({'error': f'创建学生档案失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Create Relationship ---
        try:
            StudentTeacherRelationship.objects.create(student=student, teacher=teacher)
        except Exception as e:
            student.delete() # Rollback student creation
            user.delete() # Rollback user creation
            return Response({'error': f'建立师生关系失败: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # --- Return Success Response ---
        # Use the serializer to return the newly created student's data
        # Important: Fetch the full student object again to serialize related fields correctly
        created_student = Student.objects.get(pk=student.pk)
        response_serializer = StudentSerializer(created_student, context={'request': request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsTeacher], url_path='remove-student')
    def remove_student(self, request):
        """
        解除登录教师与指定学生的关系
        Expects: {'student_id': <student_id>} in request body
        """
        teacher = request.user.teacher_profile
        student_id = request.data.get('student_id')

        if not student_id:
            return Response({'error': '缺少 student_id'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure the student exists
            student = Student.objects.get(pk=student_id)
            # Find and delete the relationship
            relationship = StudentTeacherRelationship.objects.filter(student=student, teacher=teacher)
            if relationship.exists():
                relationship.delete()
                # Optionally: Delete the student user if they have no other teachers?
                # For now, just remove the relationship.
                return Response({'message': '成功解除师生关系'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': '未找到该师生关系'}, status=status.HTTP_404_NOT_FOUND)

        except Student.DoesNotExist:
            return Response({'error': '未找到指定ID的学生'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': f'移除学生时出错: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StudentViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学生信息查看或编辑 (对教师和学生本身)
    """
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated] # Base permission

    def get_queryset(self):
        """
        - 如果是管理员，返回所有学生。
        - 如果是教师，返回其关联的所有学生。
        - 如果是学生，返回其自己的档案。
        """
        user = self.request.user

        # Pre-fetch related user and teacher data for efficiency
        # Add .order_by('id') for consistent pagination
        queryset = Student.objects.select_related('user').prefetch_related('teacher_relationships__teacher__user').all().order_by('id')

        if user.is_staff:
            return queryset # Admin sees all
        elif hasattr(user, 'teacher_profile'):
             # Filter students linked to this teacher via the relationship model
             teacher_profile = user.teacher_profile
             # Get IDs of students related to this teacher
             related_student_ids = StudentTeacherRelationship.objects.filter(
                 teacher=teacher_profile
             ).values_list('student_id', flat=True)
             return queryset.filter(id__in=related_student_ids)
        elif hasattr(user, 'student_profile'):
             # Student sees their own profile
             return queryset.filter(user=user)
        else:
             # Other authenticated users (if any) see nothing via this endpoint
             return queryset.none()

    # Apply more specific permissions for object-level actions
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'retrieve']:
             self.permission_classes = [IsAuthenticated, IsStudentOwnerOrRelatedTeacherOrAdmin]
        else: # list, create (though creation is handled by teacher now)
             self.permission_classes = [IsAuthenticated]
        return super().get_permissions()