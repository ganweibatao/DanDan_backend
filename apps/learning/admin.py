from django.contrib import admin
from .models import LearningPlan, WordLearningStage

@admin.register(LearningPlan)
class LearningPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'teacher', 'vocabulary_book', 'start_date', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'teacher', 'vocabulary_book')
    search_fields = ('student__user__username', 'teacher__user__username', 'vocabulary_book__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(WordLearningStage)
class WordLearningStageAdmin(admin.ModelAdmin):
    list_display = ('get_word', 'get_plan_id', 'learning_plan', 'current_stage', 'start_date', 'next_review_date', 'last_reviewed_at')
    list_filter = ('current_stage', 'start_date', 'next_review_date')
    search_fields = ('book_word__word_basic__word', 'learning_plan__student__user__username')
    ordering = ('-updated_at',)
    
    def get_word(self, obj):
        return obj.book_word.word_basic.word if obj.book_word and obj.book_word.word_basic else "Unknown Word"
    get_word.short_description = '单词'
    
    def get_plan_id(self, obj):
        return obj.learning_plan.id if obj.learning_plan else None
    get_plan_id.short_description = 'Plan ID'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'learning_plan__student__user', 
            'book_word'
        )