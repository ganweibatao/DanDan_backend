from rest_framework import serializers
from .models import Game, GameResult

class GameSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Game
        fields = ['id', 'name', 'description', 'game_type', 'course', 'course_title',
                 'words', 'difficulty_level', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class GameResultSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    game_name = serializers.CharField(source='game.name', read_only=True)
    
    class Meta:
        model = GameResult
        fields = ['id', 'user', 'username', 'game', 'game_name', 
                 'score', 'time_spent', 'words_learned', 'created_at']
        read_only_fields = ['created_at'] 