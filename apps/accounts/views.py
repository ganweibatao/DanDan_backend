from django.contrib.auth.models import User
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from .models import Teacher, Student, StudentTeacherRelationship, EmailVerificationCode
from .serializers import UserSerializer, TeacherSerializer, StudentSerializer
from .serializers import EmailSerializer, EmailVerificationCodeSerializer, VerifyEmailCodeSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .permissions import IsTeacher, IsStudent, IsTeacherOrAdmin, IsTeacherOwnerOrAdmin, IsStudentOwnerOrRelatedTeacherOrAdmin
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
import random
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.tracking.models import UserDurationLog
from django.db.models import Sum
import uuid
from urllib.parse import quote
import requests
from django.http import HttpResponseRedirect, JsonResponse
from social_django.models import UserSocialAuth
import time
import logging
from rest_framework.views import APIView
from social_django.utils import psa
import os
import datetime
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
# from utils.email_service import EmailService  # 暂时注释掉

# 获取日志记录器
logger = logging.getLogger('django')

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
            
        # 允许用户名重复，不再校验唯一性
        # if User.objects.filter(username=username).exists():
        #      return Response({'error': f"用户名 '{username}' 已存在"}, status=status.HTTP_400_BAD_REQUEST)
            
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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        response = Response({'message': '已退出登录'}, status=status.HTTP_200_OK)
        response.delete_cookie('auth_token')  # 清除 token cookie
        # 如果你还用 session，也可以加上
        from django.contrib.auth import logout as django_logout
        django_logout(request)
        return response

    @action(detail=False, methods=['GET'], permission_classes=[permissions.AllowAny])
    def wechat_qrcode(self, request):
        """生成微信扫码授权URL（不再需要轮询）"""
        # 生成用于防CSRF的state参数
        state_value = uuid.uuid4().hex # Renamed state to state_value for clarity
        # 使用固定的 key 存储 state_value
        request.session['wechat_auth_state_key'] = state_value 
        request.session.set_expiry(300) # 设置 state 在 session 中5分钟后过期

        # 动态构建redirect_uri
        scheme = request.scheme
        host = request.get_host()
        redirect_path = '/api/accounts/users/wechat_callback/' # 与urls.py一致
        redirect_uri = f"{scheme}://{host}{redirect_path}"

        # 构建微信授权URL
        # 注意：appid需要替换为你自己的
        appid = settings.SOCIAL_AUTH_WEIXIN_KEY
        auth_url = f"https://open.weixin.qq.com/connect/qrconnect?appid={appid}&redirect_uri={quote(redirect_uri)}&response_type=code&scope=snsapi_login&state={state_value}#wechat_redirect" # Pass state_value in URL

        logger.info(f"生成微信扫码授权URL: state={state_value}, redirect_uri={redirect_uri}")

        return Response({
            'auth_url': auth_url
            # 不再需要返回 state 给前端，因为它由后端 session 管理
        })

    @action(detail=False, methods=['GET'], permission_classes=[permissions.AllowAny]) # 注意：回调通常不需要 CSRF 保护，但 state 验证是必须的
    def wechat_callback(self, request):
        """微信回调接口，处理授权结果并重定向到前端"""
        code = request.GET.get('code')
        state_from_wechat = request.GET.get('state')
        
        logger.info(f"微信回调接收到 code: {code}, state: {state_from_wechat}")

        # 0. 初始化 created 变量
        created = False

        # 1. 验证 state
        # 使用固定的 key 'wechat_auth_state_key' 来获取之前存储的 state_value
        expected_state_value = request.session.pop('wechat_auth_state_key', None) 

        if not code or not state_from_wechat:
            logger.error("微信回调缺少必要参数 code 或 state")
            return redirect('/login?error=wx_callback_missing_params') # 前端需要处理这个错误

        if expected_state_value is None:
            logger.warning(f"微信回调 state 验证失败：session 中未找到期望的 state 或已过期。收到的 state: {state_from_wechat}")
            return redirect('/login?error=wx_callback_state_expired') 
        
        if state_from_wechat != expected_state_value:
            logger.warning(f"微信回调 state 验证失败：收到的 state ({state_from_wechat}) 与期望的 state ({expected_state_value}) 不匹配")
            return redirect('/login?error=wx_callback_state_mismatch')

        logger.info(f"微信回调 state 验证成功: {state_from_wechat}")

        try:
            # 用code换取access_token和openid
            # 注意：appid 和 secret 需要替换为你自己的
            appid = settings.SOCIAL_AUTH_WEIXIN_KEY
            secret = settings.SOCIAL_AUTH_WEIXIN_SECRET
            
            token_response = requests.get(
                'https://api.weixin.qq.com/sns/oauth2/access_token',
                params={
                    'appid': appid,
                    'secret': secret,
                    'code': code,
                    'grant_type': 'authorization_code'
                }
            )
            token_response.raise_for_status() # 如果请求失败则抛出HTTPError
            wx_data = token_response.json()

            if 'errcode' in wx_data:
                logger.error(f"微信API错误 (获取token): {wx_data.get('errmsg')}")
                error_msg = quote(wx_data.get('errmsg', '微信API未知错误'))
                return redirect(f'/login?error=wx_api_token&msg={error_msg}')

            access_token = wx_data['access_token']
            openid = wx_data['openid']

            # 获取微信用户信息
            user_info_response = requests.get(
                'https://api.weixin.qq.com/sns/userinfo',
                params={
                    'access_token': access_token,
                    'openid': openid,
                    'lang': 'zh_CN'
                }
            )

            # 强制使用 UTF-8 解码
            user_info_response.encoding = 'utf-8'

            # 然后再调用 .json()
            user_info = user_info_response.json()

            if 'errcode' in user_info:
                logger.error(f"微信API错误 (获取用户信息): {user_info.get('errmsg')}")
                error_msg = quote(user_info.get('errmsg', '微信API未知错误'))
                return redirect(f'/login?error=wx_api_userinfo&msg={error_msg}')

            # 查找已绑定的用户，或创建新用户
            # 使用 social_django 的 UserSocialAuth 模型来简化处理
            try:
                social_user = UserSocialAuth.objects.get(provider='weixin', uid=openid)
                user = social_user.user
                logger.info(f"微信登录：用户已存在 {user.username} (uid: {openid})")
            except UserSocialAuth.DoesNotExist:
                # 创建新用户并关联
                email = user_info.get('email', '')
                
                with transaction.atomic(): # 确保用户和 social_user 的创建是原子的
                    user, created = User.objects.get_or_create(
                        username=user_info.get('nickname', f"wx_{openid[:12]}"), # 用微信昵称作为用户名
                        defaults={
                            'email': email,
                            'first_name': user_info.get('nickname', ''),
                            # 密码可以设为不可用，因为他们是通过微信登录的
                            # user.set_unusable_password() # 最好在创建后调用
                        }
                    )
                    if created:
                        print("[WeChat] user_info:", user_info)
                        user.set_unusable_password()
                        user.save()
                        logger.info(f"微信登录：创建新用户 {user.username} (uid: {openid})")
                        gender_map = {1: 'female', 0: 'male'}
                        # 兼容字符串或整数的 sex 值
                        gender_value = gender_map.get(user_info.get('sex'), 'other')
                        # 下载微信头像到本地
                        avatar_url = user_info.get('headimgurl', '')
                        avatar_file = None
                        if avatar_url:
                            try:
                                avatar_resp = requests.get(avatar_url, timeout=5)
                                if avatar_resp.status_code == 200:
                                    ext = os.path.splitext(avatar_url)[-1][:5] or '.jpg'
                                    avatar_name = f"avatars/wx_{user.id}{ext}"
                                    avatar_file = ContentFile(avatar_resp.content)
                                    avatar_path = default_storage.save(avatar_name, avatar_file)
                                else:
                                    avatar_path = ''
                            except Exception as e:
                                logger.warning(f"下载微信头像失败: {e}")
                                avatar_path = ''
                        else:
                            avatar_path = ''
                        Teacher.objects.create(
                            user=user,
                            avatar=avatar_path,
                            real_name=user_info.get('nickname', ''),
                            province=user_info.get('province', ''),
                            city=user_info.get('city', ''),
                            gender=gender_value
                        )
                    
                    social_user, social_created = UserSocialAuth.objects.update_or_create(
                        user=user,
                        provider='weixin',
                        uid=openid,
                        defaults={'extra_data': user_info} # 存储原始微信用户信息，包括 access_token, openid 等
                    )
                    if social_created and not created: # 用户已存在，但首次绑定微信
                        logger.info(f"微信登录：用户 {user.username} 首次绑定微信 (uid: {openid})")


            # 生成 DRF Token (如果你的API主要用TokenAuthentication)
            # 或者直接使用Django的session登录 (如果你的API用SessionAuthentication)
            # 当前后端是 CookieTokenAuthentication, Token 会被设置到 cookie
            
            token, _ = Token.objects.get_or_create(user=user)

            # 使用Django的login函数，这会设置session，对于依赖session的Django功能有用
            login(request, user, backend='django.contrib.auth.backends.ModelBackend') # 指定backend避免冲突
            
            # 构建前端重定向响应
            if created:
                frontend_redirect_url = '/settings/profile'
            else:
                frontend_redirect_url = '/teacher'
            response = redirect(frontend_redirect_url)

            # 设置认证Cookie (auth_token)
            response.set_cookie(
                key='auth_token',
                value=token.key,
                httponly=True,
                samesite='Lax', # 'Strict' 更安全，但 'Lax' 更兼容
                max_age=settings.SESSION_COOKIE_AGE if hasattr(settings, 'SESSION_COOKIE_AGE') else 60*60*24*14,  # 例如两周
                path='/',
                secure=not settings.DEBUG # 在生产环境 (HTTPS) 应设置为 True
            )

            logger.info(f"微信登录成功：用户 {user.username}, 重定向到 {frontend_redirect_url}")
            return response

        except requests.exceptions.RequestException as e:
            logger.error(f"微信API请求错误: {e}")
            return redirect('/login?error=wx_api_request_failed')
        except Exception as e:
            logger.error(f"微信回调处理未知错误: {e}", exc_info=True) # exc_info=True 会记录堆栈跟踪
            return redirect('/login?error=wx_callback_server_error')

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
        # 允许用户名重复，不再校验唯一性
        # if User.objects.filter(username=username).exists():
        #      return Response({'error': f"用户名 '{username}' 已存在"}, status=status.HTTP_400_BAD_REQUEST)

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

@api_view(['POST'])
@permission_classes([AllowAny])
def send_email_code(request):
    """
    发送邮箱验证码API
    
    请求参数:
    - email: 邮箱地址
    
    返回:
    - 成功: {success: true, message: '验证码已发送'}
    - 失败: {success: false, error: '错误信息'}
    """
    serializer = EmailSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': '无效的邮箱地址'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    
    # 检查同一邮箱是否频繁请求验证码（限流）
    cache_key = f"email_send_limit:{email}"
    if cache.get(cache_key):
        return Response({
            'success': False,
            'error': f'同一邮箱发送过于频繁，请{settings.EMAIL_SEND_INTERVAL}秒后再试'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # 生成6位数字验证码
    code = ''.join(random.choice('0123456789') for _ in range(settings.EMAIL_CODE_LENGTH))
    
    # 设置过期时间
    expires_at = timezone.now() + datetime.timedelta(minutes=settings.EMAIL_CODE_EXPIRE_MINUTES)
    
    # 保存验证码记录
    try:
        EmailVerificationCode.objects.create(
            email=email,
            code=code,
            expires_at=expires_at
        )
    except Exception as e:
        logger.error(f"保存验证码失败: {email}, 错误: {e}")
        return Response({
            'success': False,
            'error': '服务器错误，请稍后再试'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # 异步发送邮件
    try:
        EmailService.send_verification_code(email, code)
        
        # 设置发送间隔限制（防止频繁请求）
        cache.set(cache_key, 1, settings.EMAIL_SEND_INTERVAL)
        
        return Response({
            'success': True,
            'message': '验证码已发送，有效期5分钟'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"邮件发送出错: {email}, 错误: {e}")
        return Response({
            'success': False,
            'error': '邮件发送失败，请稍后再试'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_code(request):
    """
    验证邮箱验证码API
    
    请求参数:
    - email: 邮箱地址
    - code: 验证码
    
    返回:
    - 成功: {success: true, message: '验证通过'}
    - 失败: {success: false, error: '错误信息'}
    """
    serializer = VerifyEmailCodeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': '请提供有效的邮箱和验证码'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    
    # 查询最新的未使用验证码
    try:
        verification = EmailVerificationCode.objects.filter(
            email=email,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()
        
        if not verification:
            return Response({
                'success': False,
                'error': '验证码无效或已过期'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 标记验证码已使用
        verification.is_used = True
        verification.save()
        
        return Response({
            'success': True,
            'message': '验证通过'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"验证码校验出错: {email}, code: {code}, 错误: {e}")
        return Response({
            'success': False,
            'error': '服务器错误，请稍后再试'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    通过邮箱验证码重置用户密码

    请求参数:
    - email: 邮箱地址
    - code: 邮箱验证码
    - new_password: 新密码

    返回:
    - 成功: {success: true, message: '密码已重置'}
    - 失败: {success: false, error: '错误信息'}
    """
    email = request.data.get('email')
    code = request.data.get('code')
    new_password = request.data.get('new_password')

    # 基础校验
    if not email or not code or not new_password:
        return Response({
            'success': False,
            'error': '请提供邮箱、验证码和新密码'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 再次校验邮箱格式
    from django.core.validators import validate_email as django_validate_email
    from django.core.exceptions import ValidationError as DjangoValidationError
    try:
        django_validate_email(email)
    except DjangoValidationError:
        return Response({'success': False, 'error': '邮箱格式不正确'}, status=status.HTTP_400_BAD_REQUEST)

    # 校验验证码有效性
    try:
        verification = EmailVerificationCode.objects.filter(
            email=email,
            code=code,
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()
        if not verification:
            return Response({'success': False, 'error': '验证码无效或已过期'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"验证码查询失败: {email}, code: {code}, 错误: {e}")
        return Response({'success': False, 'error': '服务器错误，请稍后再试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # 获取用户并重置密码
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'success': False, 'error': '未找到该邮箱对应的用户'}, status=status.HTTP_404_NOT_FOUND)

    # 验证新密码强度
    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return Response({'success': False, 'error': '新密码不符合要求: ' + '; '.join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user.set_password(new_password)
        user.save()
        # 标记验证码已使用
        verification.is_used = True
        verification.save()
    except Exception as e:
        logger.error(f"重置密码失败: {email}, 错误: {e}")
        return Response({'success': False, 'error': '重置密码失败，请稍后再试'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'success': True, 'message': '密码已重置'}, status=status.HTTP_200_OK)