from django.contrib import admin
from .models import Category, Word, Course

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ('word', 'category', 'difficulty_level', 'created_at')
    search_fields = ('word', 'definition', 'example')
    list_filter = ('category', 'difficulty_level', 'created_at')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'category', 'difficulty_level', 'is_active', 'created_at')
    search_fields = ('title', 'description', 'teacher__username')
    list_filter = ('category', 'difficulty_level', 'is_active', 'created_at')
    filter_horizontal = ('words',) 