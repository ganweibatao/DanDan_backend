from django.contrib import admin
from .models import UserDurationLog
from datetime import datetime
from zoneinfo import ZoneInfo

@admin.register(UserDurationLog)
class UserDurationLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'display_student', 'type', 'duration',
        'formatted_client_start_time', 'formatted_client_end_time', 'formatted_created_at'
    )
    list_filter = (
        'type', 'user', 'student',
        ('client_start_time', admin.DateFieldListFilter),
        ('client_end_time', admin.DateFieldListFilter),
        ('created_at', admin.DateFieldListFilter),
    )
    search_fields = ('user__username', 'student__user__username')
    ordering = ('-created_at',)

    def display_student(self, obj):
        if obj.type == 'teaching' and obj.student:
            return obj.student
        return '-'
    display_student.short_description = '关联学生'

    def formatted_client_start_time(self, obj):
        if obj.client_start_time:
            bj_time = obj.client_start_time.astimezone(ZoneInfo('Asia/Shanghai'))
            return bj_time.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    formatted_client_start_time.short_description = '前端开始时间'

    def formatted_client_end_time(self, obj):
        if obj.client_end_time:
            bj_time = obj.client_end_time.astimezone(ZoneInfo('Asia/Shanghai'))
            return bj_time.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    formatted_client_end_time.short_description = '前端结束时间'

    def formatted_created_at(self, obj):
        if obj.created_at:
            bj_time = obj.created_at.astimezone(ZoneInfo('Asia/Shanghai'))
            return bj_time.strftime('%Y-%m-%d %H:%M:%S')
        return '-'
    formatted_created_at.short_description = '入库时间'
