from django.contrib import admin
from .models import LearningPlan, LearningUnit, UnitReview

@admin.register(LearningPlan)
class LearningPlanAdmin(admin.ModelAdmin):
    list_display = ('student', 'teacher', 'vocabulary_book', 'words_per_day', 'start_date', 'is_active', 'created_at', 'updated_at')
    search_fields = ('student__user__username', 'teacher__user__username', 'vocabulary_book__name')
    list_filter = ('is_active', 'teacher', 'start_date')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LearningUnit)
class LearningUnitAdmin(admin.ModelAdmin):
    list_display = ('learning_plan', 'unit_number', 'start_word_order', 'end_word_order', 'expected_learn_date', 'is_learned', 'learned_at', 'created_at', 'updated_at')
    search_fields = ('learning_plan__student__user__username',)
    list_filter = ('is_learned', 'expected_learn_date')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UnitReview)
class UnitReviewAdmin(admin.ModelAdmin):
    list_display = ('learning_unit', 'review_date', 'review_order', 'is_completed', 'completed_at', 'created_at', 'updated_at')
    search_fields = ('learning_unit__learning_plan__student__user__username',)
    list_filter = ('is_completed', 'review_date', 'review_order')
    readonly_fields = ('created_at', 'updated_at') 