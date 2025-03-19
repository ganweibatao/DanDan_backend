from rest_framework import serializers
from .models import Category, Word, Course

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class WordSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Word
        fields = ['id', 'word', 'pronunciation', 'definition', 'example', 
                 'category', 'category_name', 'difficulty_level', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class CourseSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.username', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'teacher', 'teacher_name', 
                 'category', 'category_name', 'words', 'difficulty_level', 
                 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at'] 