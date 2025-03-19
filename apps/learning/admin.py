from django.contrib import admin
from .models import UserProgress, Session, StudyRecord

@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'current_level', 'total_study_time', 'last_study_date')
    search_fields = ('user__username', 'course__title')
    list_filter = ('current_level', 'last_study_date')
    filter_horizontal = ('completed_words',)

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'start_time', 'end_time', 'duration')
    search_fields = ('user__username', 'course__title')
    list_filter = ('start_time',)
    filter_horizontal = ('words_learned',)

@admin.register(StudyRecord)
class StudyRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'word', 'session', 'is_correct', 'response_time', 'created_at')
    search_fields = ('user__username', 'word__word')
    list_filter = ('is_correct', 'created_at') 