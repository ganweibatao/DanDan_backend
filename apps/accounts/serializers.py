from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Teacher, Student

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']
        read_only_fields = ['is_staff']
        
class TeacherSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Teacher
        fields = ['id', 'user', 'username', 'email', 'avatar', 'bio', 
                 'title', 'specialties', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Student
        fields = ['id', 'user', 'username', 'email', 'avatar', 'bio',
                 'level', 'interests', 'learning_goal', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at'] 