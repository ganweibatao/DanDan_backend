from django.db import models
from django.contrib.auth.models import User
from apps.vocabulary.models import Word, Course

class Game(models.Model):
    """游戏"""
    GAME_TYPES = [
        ('word_match', '单词匹配'),
        ('spelling', '拼写练习'),
        ('memory', '记忆游戏'),
        ('quiz', '单词测验'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    game_type = models.CharField(max_length=20, choices=GAME_TYPES)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='games')
    words = models.ManyToManyField(Word, related_name='games')
    difficulty_level = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class GameResult(models.Model):
    """游戏结果"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='game_results')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='results')
    score = models.IntegerField()
    time_spent = models.IntegerField()  # 游戏时长（秒）
    words_learned = models.ManyToManyField(Word, related_name='game_results')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username}'s result in {self.game.name}" 