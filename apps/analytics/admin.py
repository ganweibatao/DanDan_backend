from django.contrib import admin
from .models import LearningStat, Report

@admin.register(LearningStat)
class LearningStatAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'date', 'words_learned', 'correct_rate', 'study_time')
    search_fields = ('user__username', 'course__title')
    list_filter = ('date',)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('user', 'report_type', 'course', 'start_date', 'end_date', 'total_words', 'average_correct_rate', 'total_study_time')
    search_fields = ('user__username', 'course__title')
    list_filter = ('report_type', 'start_date', 'end_date') 