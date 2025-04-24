from rest_framework import permissions
from .models import StudentTeacherRelationship

class IsTeacher(permissions.BasePermission):
    """
    允许访问的用户必须关联到一个 Teacher 实例。
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'teacher_profile')

class IsStudent(permissions.BasePermission):
    """
    允许访问的用户必须关联到一个 Student 实例。
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'student_profile')

class IsTeacherOrAdmin(permissions.BasePermission):
    """
    允许教师或管理员访问。
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_staff or hasattr(request.user, 'teacher_profile')
        )

class IsTeacherOwnerOrAdmin(permissions.BasePermission):
    """
    允许对象所有者(教师)或管理员进行编辑。
    """
    def has_object_permission(self, request, view, obj):
        # 允许 GET, HEAD, OPTIONS 请求
        if request.method in permissions.SAFE_METHODS:
            return True
        # 写权限只给对象的所有者或管理员
        return obj.user == request.user or request.user.is_staff

class IsStudentOwnerOrRelatedTeacherOrAdmin(permissions.BasePermission):
    """
    允许学生本人、关联的教师或管理员访问和编辑（读写）。
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for owner, related teacher, or admin
        is_owner = obj.user == request.user
        is_admin = request.user.is_staff
        is_related_teacher = False
        if hasattr(request.user, 'teacher_profile'):
            # Check if a relationship exists
            is_related_teacher = StudentTeacherRelationship.objects.filter(
                student=obj,
                teacher=request.user.teacher_profile
            ).exists()

        # 读写权限都允许学生本人、关联老师、管理员
        return is_owner or is_admin or is_related_teacher

class IsRelatedTeacherOrAdmin(permissions.BasePermission):
    """
    仅允许与学生有关联关系的教师或管理员进行编辑。
    """
    def has_object_permission(self, request, view, obj):
        # 检查是否是管理员
        is_admin = request.user.is_staff
        
        # 检查是否是关联教师
        is_related_teacher = False
        if hasattr(request.user, 'teacher_profile'):
            # 检查是否存在师生关系
            is_related_teacher = StudentTeacherRelationship.objects.filter(
                student=obj,
                teacher=request.user.teacher_profile
            ).exists()
        
        # 只允许关联教师或管理员进行编辑
        return is_related_teacher or is_admin 