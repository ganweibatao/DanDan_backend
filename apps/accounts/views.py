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
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
import random
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.tracking.models import UserDurationLog
from django.db.models import Sum

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

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='initiate-email-change')
    def initiate_email_change(self, request):
        """
        Initiates the email change process.
        Sends a verification code to the new email address.
        Expects: {"new_email": "user@example.com"}
        """
        new_email = request.data.get('new_email')
        user = request.user

        if not new_email:
            return Response({'error': 'New email address is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate email format (basic check)
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(new_email)
        except ValidationError:
            return Response({'error': 'Invalid email format.'}, status=status.HTTP_400_BAD_REQUEST)

        if new_email == user.email:
            return Response({'error': 'New email cannot be the same as the current email.'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if new email is already taken by another user
        if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
            return Response({'error': 'This email address is already in use.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate verification code
        verification_code = str(random.randint(100000, 999999))
        cache_key = f'email_change_code_{user.id}'
        # Store code and new email in cache for 10 minutes
        cache.set(cache_key, {'code': verification_code, 'new_email': new_email}, timeout=600)

        # Send verification email (or print to console in development)
        try:
            subject = 'Verify your new email address'
            message = f'Your verification code is: {verification_code}\nThis code will expire in 10 minutes.'
            from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'webmaster@localhost' # Fallback needed if not set
            send_mail(subject, message, from_email, [new_email])
            print(f"--- Email Change Verification ---")
            print(f"To: {new_email}")
            print(f"Subject: {subject}")
            print(f"Code: {verification_code}")
            print(f"-------------------------------")
        except Exception as e:
            print(f"Error sending email: {e}") # Log error
            # Optionally inform user email sending failed, but proceed with cache logic
            # return Response({'error': 'Failed to send verification email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        return Response({'message': 'Verification code sent to the new email address.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='confirm-email-change')
    def confirm_email_change(self, request):
        """
        Confirms the email change using the verification code.
        Expects: {"code": "123456", "new_email": "user@example.com"}
        """
        code = request.data.get('code')
        new_email_provided = request.data.get('new_email') # Get new email from request for safety
        user = request.user

        if not code or not new_email_provided:
            return Response({'error': 'Verification code and new email are required.'}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f'email_change_code_{user.id}'
        cached_data = cache.get(cache_key)

        if not cached_data:
            return Response({'error': 'Verification code expired or not found. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        if cached_data.get('code') != code:
            return Response({'error': 'Invalid verification code.'}, status=status.HTTP_400_BAD_REQUEST)

        # Double check the email associated with the code matches the one provided
        if cached_data.get('new_email') != new_email_provided:
             return Response({'error': 'Email address mismatch during confirmation.'}, status=status.HTTP_400_BAD_REQUEST)


        # Check again if the email is taken (race condition check)
        if User.objects.filter(email=new_email_provided).exclude(pk=user.pk).exists():
            cache.delete(cache_key) # Clean up cache
            return Response({'error': 'This email address was taken while you were verifying.'}, status=status.HTTP_400_BAD_REQUEST)

        # Update user's email
        try:
            user.email = new_email_provided
            user.save(update_fields=['email'])
            cache.delete(cache_key) # Clean up cache
            return Response({'message': 'Email address updated successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
             print(f"Error saving user email: {e}")
             return Response({'error': 'Failed to update email address.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='change-password')
    def change_password(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        if not old_password or not new_password:
            return Response({'error': '请提供原密码和新密码'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(old_password):
            return Response({'error': '原密码错误'}, status=status.HTTP_400_BAD_REQUEST)
        if old_password == new_password:
            return Response({'error': '新密码不能和原密码相同'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response({'error': '新密码不符合要求: ' + '; '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_password)
        user.save()
        return Response({'message': '密码修改成功'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated], url_path='delete-account')
    def delete_account(self, request):
        user = request.user
        password = request.data.get('password')
        if not password:
            return Response({'error': '请提供密码'}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(password):
            return Response({'error': '密码错误'}, status=status.HTTP_400_BAD_REQUEST)
        user.delete()
        return Response({'message': '账户已删除'}, status=status.HTTP_204_NO_CONTENT)

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

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsTeacher], url_path='total-teaching-duration')
    def total_teaching_duration(self, request):
        """
        获取当前登录教师的总授课时长（小时）
        """
        user = request.user
        
        # 确保用户是教师 (虽然 IsTeacher 权限类已经处理，这里可以加一层保险)
        if not hasattr(user, 'teacher_profile'):
            return Response({'error': '用户不是教师'}, status=status.HTTP_403_FORBIDDEN)
            
        # 查询该教师的所有授课记录并计算总时长（秒）
        aggregation = UserDurationLog.objects.filter(
            user=user, 
            type='teaching'
        ).aggregate(total_seconds=Sum('duration'))
        
        total_seconds = aggregation.get('total_seconds') or 0
        
        # 将秒转换为小时，保留两位小数
        total_hours = round(total_seconds / 3600, 2)
        
        return Response({'total_teaching_hours': total_hours}, status=status.HTTP_200_OK)

class StudentViewSet(viewsets.ModelViewSet):
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

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsTeacher], url_path='learning-hours')
    def learning_hours(self, request):
        """
        教师批量获取自己所有学生的学习时长（小时），未找到则为0.00
        返回: [{student_id: int, learning_hours: float}]
        """
        teacher = request.user.teacher_profile
        # 获取所有关联学生ID
        student_ids = list(StudentTeacherRelationship.objects.filter(teacher=teacher).values_list('student_id', flat=True))
        # 查询这些学生的学习时长（秒）
        logs = UserDurationLog.objects.filter(user__student_profile__id__in=student_ids, type='learning')
        agg = logs.values('user__student_profile__id').annotate(total_seconds=Sum('duration'))
        # 构建 student_id -> hours 映射
        id_to_hours = {item['user__student_profile__id']: round((item['total_seconds'] or 0) / 3600, 2) for item in agg}
        # 保证所有学生都返回
        result = [
            {'student_id': sid, 'learning_hours': id_to_hours.get(sid, 0.00)}
            for sid in student_ids
        ]
        return Response(result)