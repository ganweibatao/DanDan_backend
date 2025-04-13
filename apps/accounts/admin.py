from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Teacher, Student, StudentTeacherRelationship

# --- Define Inlines for Relationships ---

class StudentRelationshipInline(admin.TabularInline):
    """Inline view for students related to a teacher."""
    model = StudentTeacherRelationship
    fk_name = 'teacher'  # Explicitly state the foreign key to Teacher
    extra = 0  # Don't show extra blank forms
    fields = ('student', 'created_at') # Fields to display in the inline row
    readonly_fields = ('created_at',) # Make creation time read-only
    autocomplete_fields = ['student'] # Use autocomplete for selecting students (if adding allowed)
    verbose_name = "关联学生"
    verbose_name_plural = "关联学生"
    # To make it purely display, uncomment below and remove autocomplete_fields
    # readonly_fields = ('student', 'created_at')
    # can_delete = False
    # max_num = 0 # Hide 'Add another' button


class TeacherRelationshipInline(admin.TabularInline):
    """Inline view for teachers related to a student."""
    model = StudentTeacherRelationship
    fk_name = 'student' # Explicitly state the foreign key to Student
    extra = 0
    fields = ('teacher', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ['teacher']
    verbose_name = "关联教师"
    verbose_name_plural = "关联教师"
    # To make it purely display, uncomment below and remove autocomplete_fields
    # readonly_fields = ('teacher', 'created_at')
    # can_delete = False
    # max_num = 0


# --- Update ModelAdmins ---

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'specialties', 'university', 'teaching_years', 'work_status', 'created_at')
    search_fields = ('user__username', 'user__email', 'title', 'specialties', 'university')
    list_filter = ('work_status', 'education_level', 'english_level', 'created_at')
    inlines = [StudentRelationshipInline] # Add the inline here

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'personality_traits', 'gender', 'created_at')
    search_fields = ('user__username', 'user__email', 'level', 'personality_traits')
    list_filter = ('level', 'gender', 'created_at')
    inlines = [TeacherRelationshipInline] # Add the inline here

@admin.register(StudentTeacherRelationship)
class StudentTeacherRelationshipAdmin(admin.ModelAdmin):
    list_display = ('student', 'teacher', 'created_at')
    list_filter = ('teacher',)
    search_fields = ('student__user__username', 'teacher__user__username')
    autocomplete_fields = ['student', 'teacher']

# 如果你之前有自定义 UserAdmin，保留它
class TeacherInline(admin.StackedInline):
    model = Teacher
    can_delete = False
    verbose_name_plural = '教师信息'

class StudentInline(admin.StackedInline):
    model = Student
    can_delete = False
    verbose_name_plural = '学生信息'

class UserAdmin(BaseUserAdmin):
    inlines = (TeacherInline, StudentInline)

# 取消注册默认的 User admin，然后注册自定义的
admin.site.unregister(User)
admin.site.register(User, UserAdmin) 