from rest_framework import serializers
from .models import UserProgress, Session, StudyRecord

class UserProgressSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = UserProgress
        fields = ['id', 'user', 'username', 'course', 'course_title', 
                 'completed_words', 'current_level', 'total_study_time', 
                 'last_study_date', 'created_at', 'updated_at']
        read_only_fields = ['last_study_date', 'created_at', 'updated_at']

class SessionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Session
        fields = ['id', 'user', 'username', 'course', 'course_title', 
                 'start_time', 'end_time', 'duration', 'words_learned']
        read_only_fields = ['start_time']

class StudyRecordSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    word_text = serializers.CharField(source='word.word', read_only=True)
    
    class Meta:
        model = StudyRecord
        fields = ['id', 'user', 'username', 'word', 'word_text', 
                 'session', 'is_correct', 'response_time', 'created_at']
        read_only_fields = ['created_at'] 