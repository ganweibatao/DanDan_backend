from django.db import models
from django.conf import settings

# Create your models here.

class UserDurationLog(models.Model):
    TYPE_CHOICES = (
        ('learning', '学习'),
        ('teaching', '授课'),
        ('other', '其他'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='duration_logs', verbose_name='用户')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name='类型')
    duration = models.PositiveIntegerField(verbose_name='时长（秒）')
    client_start_time = models.DateTimeField(null=True, blank=True, verbose_name='前端开始时间')
    client_end_time = models.DateTimeField(null=True, blank=True, verbose_name='前端结束时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='入库时间')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'type', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['client_start_time']),
        ]
        verbose_name = '用户时长日志'
        verbose_name_plural = '用户时长日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.type} - {self.duration}s @ {self.created_at}"
