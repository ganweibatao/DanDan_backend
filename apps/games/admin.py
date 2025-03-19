from django.contrib import admin
from .models import Game, GameResult

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'game_type', 'course', 'difficulty_level', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'course__title')
    list_filter = ('game_type', 'difficulty_level', 'is_active', 'created_at')
    filter_horizontal = ('words',)

@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'game', 'score', 'time_spent', 'created_at')
    search_fields = ('user__username', 'game__name')
    list_filter = ('created_at',)
    filter_horizontal = ('words_learned',) 