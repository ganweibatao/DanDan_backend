from django.db import models
from django.contrib.auth.models import User
from apps.vocabulary.models import Word, Course

class UserProgress(models.Model):
    """用户学习进度"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='progress')
    completed_words = models.ManyToManyField(Word, related_name='completed_by')
    current_level = models.IntegerField(default=1)
    total_study_time = models.IntegerField(default=0)  # 总学习时间（分钟）
    last_study_date = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"{self.user.username}'s progress in {self.course.title}"

class Session(models.Model):
    """学习会话"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # 会话时长（分钟）
    words_learned = models.ManyToManyField(Word, related_name='sessions')
    
    def __str__(self):
        return f"{self.user.username}'s session in {self.course.title}"

class StudyRecord(models.Model):
    """学习记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='study_records')
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='study_records')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='records')
    is_correct = models.BooleanField()
    response_time = models.IntegerField()  # 响应时间（秒）
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s record for {self.word.word}" 