from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """用户公共信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Teacher(Profile):
    """教师信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    title = models.CharField(max_length=100, blank=True)  # 职称
    specialties = models.CharField(max_length=200, blank=True)  # 专长领域
    
    def __str__(self):
        return f"Teacher: {self.user.username}"

class Student(Profile):
    """学生信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    level = models.CharField(max_length=50, blank=True)  # 英语水平
    interests = models.CharField(max_length=200, blank=True)  # 兴趣爱好
    learning_goal = models.TextField(blank=True)  # 学习目标
    
    def __str__(self):
        return f"Student: {self.user.username}" 