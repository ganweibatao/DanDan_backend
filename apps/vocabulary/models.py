from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    """单词分类"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "categories"
    
    def __str__(self):
        return self.name

class Word(models.Model):
    """单词"""
    word = models.CharField(max_length=100)
    pronunciation = models.CharField(max_length=100, blank=True)
    definition = models.TextField()
    example = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='words')
    difficulty_level = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.word

class Course(models.Model):
    """课程"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='courses')
    words = models.ManyToManyField(Word, related_name='courses')
    difficulty_level = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title 