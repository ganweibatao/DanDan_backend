from django.contrib import admin
from .models import UserDurationLog

@admin.register(UserDurationLog)
class UserDurationLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'duration', 'client_start_time', 'client_end_time', 'created_at')
    list_filter = ('type', 'user')
    search_fields = ('user__username',)
    ordering = ('-created_at',)
