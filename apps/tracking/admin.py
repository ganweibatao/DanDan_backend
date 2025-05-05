from django.contrib import admin
from .models import UserDurationLog

@admin.register(UserDurationLog)
class UserDurationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'display_student', 'type', 'duration', 'client_start_time', 'client_end_time', 'created_at')
    list_filter = ('type', 'user', 'student')
    search_fields = ('user__username', 'student__user__username')
    ordering = ('-created_at',)

    def display_student(self, obj):
        if obj.type == 'teaching' and obj.student:
            return obj.student
        return '-'
    display_student.short_description = '关联学生'
