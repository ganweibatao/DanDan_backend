from django.contrib import admin
from .models import Teacher, Student

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'specialties', 'created_at')
    search_fields = ('user__username', 'user__email', 'title', 'specialties')
    list_filter = ('created_at',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'interests', 'created_at')
    search_fields = ('user__username', 'user__email', 'level', 'interests')
    list_filter = ('level', 'created_at') 