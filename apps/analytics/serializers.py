from rest_framework import serializers
from .models import LearningStat, Report

class LearningStatSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = LearningStat
        fields = ['id', 'user', 'username', 'course', 'course_title', 
                 'date', 'words_learned', 'correct_rate', 'study_time', 
                 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class ReportSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    
    class Meta:
        model = Report
        fields = ['id', 'user', 'username', 'report_type', 'report_type_display', 
                 'course', 'course_title', 'start_date', 'end_date', 
                 'total_words', 'average_correct_rate', 'total_study_time', 'created_at']
        read_only_fields = ['created_at'] 