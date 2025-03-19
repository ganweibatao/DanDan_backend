from django.db import models
from django.contrib.auth.models import User
from apps.vocabulary.models import Course
from apps.learning.models import StudyRecord

class LearningStat(models.Model):
    """学习统计"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_stats')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learning_stats')
    date = models.DateField()
    words_learned = models.IntegerField(default=0)
    correct_rate = models.FloatField(default=0.0)  # 正确率
    study_time = models.IntegerField(default=0)  # 学习时间（分钟）
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'course', 'date']
    
    def __str__(self):
        return f"{self.user.username}'s stats for {self.course.title} on {self.date}"

class Report(models.Model):
    """学习报告"""
    REPORT_TYPES = [
        ('daily', '每日报告'),
        ('weekly', '每周报告'),
        ('monthly', '每月报告'),
        ('course', '课程报告'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    total_words = models.IntegerField(default=0)
    average_correct_rate = models.FloatField(default=0.0)
    total_study_time = models.IntegerField(default=0)  # 总学习时间（分钟）
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s {self.get_report_type_display()} from {self.start_date} to {self.end_date}" 