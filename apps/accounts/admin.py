from django.contrib import admin
from .models import Teacher, Student

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'specialties', 'university', 'teaching_years', 'work_status', 'created_at')
    search_fields = ('user__username', 'user__email', 'title', 'specialties', 'university')
    list_filter = ('work_status', 'education_level', 'english_level', 'created_at')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'interests', 'gender', 'created_at')
    search_fields = ('user__username', 'user__email', 'level', 'interests')
    list_filter = ('level', 'gender', 'created_at') 