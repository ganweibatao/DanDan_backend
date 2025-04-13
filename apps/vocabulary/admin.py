from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Max
import csv
import io
from .models import (
    VocabularyBook, BookWord, StudentCustomization, WordBasic
)

@admin.register(WordBasic)
class WordBasicAdmin(admin.ModelAdmin):
    list_display = ('word', 'phonetic_symbol', 'created_at', 'updated_at')
    search_fields = ('word', 'phonetic_symbol')
    readonly_fields = ('created_at', 'updated_at')

class BookWordInline(admin.TabularInline):
    model = BookWord
    extra = 1
    fields = ('word_basic', 'word_order', 'meanings', 'example_sentence')

@admin.register(VocabularyBook)
class VocabularyBookAdmin(admin.ModelAdmin):
    list_display = ('name', 'word_count', 'is_system_preset', 'created_at', 'updated_at')
    list_filter = ('is_system_preset',)
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [BookWordInline]

@admin.register(BookWord)
class BookWordAdmin(admin.ModelAdmin):
    list_display = ('get_word', 'vocabulary_book', 'word_order')
    list_filter = ('vocabulary_book',)
    search_fields = ('word_basic__word', 'example_sentence')
    ordering = ('vocabulary_book', 'word_order')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_word(self, obj):
        return obj.word_basic.word if obj.word_basic else "未知单词"
    get_word.short_description = '单词'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-words/', self.admin_site.admin_view(self.import_book_words_view), name='vocabulary_bookword_import-book-words'),
        ]
        return custom_urls + urls
    
    def import_book_words_view(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            book_id = request.POST.get('vocabulary_book')
            
            if not csv_file or not book_id:
                self.message_user(request, "请提供CSV文件和选择词汇书", level=messages.ERROR)
                return redirect('..')
            
            try:
                book = VocabularyBook.objects.get(id=book_id)
                try:
                    decoded_file = csv_file.read().decode('utf-8')
                except UnicodeDecodeError:
                    # 尝试其他编码，如果UTF-8不成功
                    try:
                        decoded_file = csv_file.read().decode('gb2312')
                    except UnicodeDecodeError:
                        decoded_file = csv_file.read().decode('gbk')
                
                io_string = io.StringIO(decoded_file)
                reader = csv.DictReader(io_string)
                
                word_count = 0
                # 获取当前词汇书中最大的word_order
                max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                    Max('word_order')
                ).get('word_order__max') or 0
                
                for row in reader:
                    # 确保CSV文件包含所需字段
                    if 'word' not in row:
                        raise Exception("CSV文件格式错误。必须包含'word'列")
                    
                    # 创建或获取WordBasic
                    word_basic, word_basic_created = WordBasic.objects.get_or_create(
                        word=row['word'],
                        defaults={
                            'phonetic_symbol': row.get('phonetic_symbol', ''),
                            'uk_pronunciation': row.get('uk_pronunciation', ''),
                            'us_pronunciation': row.get('us_pronunciation', '')
                        }
                    )
                    
                    # 创建或更新单词
                    max_order += 1
                    
                    # 处理词性和释义，转换为JSON格式
                    part_of_speech = row.get('part_of_speech', '')
                    chinese_meaning = row.get('chinese_meaning', '')
                    
                    if part_of_speech and chinese_meaning:
                        meanings = [{'pos': part_of_speech, 'meaning': chinese_meaning}]
                    else:
                        meanings = []
                    
                    word, created = BookWord.objects.update_or_create(
                        vocabulary_book=book,
                        word_basic=word_basic,
                        defaults={
                            'word_order': int(row.get('word_order')) if row.get('word_order') and row.get('word_order').strip() else max_order,
                            'meanings': meanings,
                            'example_sentence': row.get('example_sentence', '')
                        }
                    )
                    word_count += 1
                
                # 更新词汇书的词汇量
                total_words = BookWord.objects.filter(vocabulary_book=book).count()
                book.word_count = total_words
                book.save()
                
                self.message_user(request, f"成功导入 {word_count} 个单词到词汇书 '{book.name}'")
                return redirect('..')
            except Exception as e:
                self.message_user(request, f"导入失败: {str(e)}", level=messages.ERROR)
                return redirect('..')
        
        # 渲染导入表单
        vocabulary_books = VocabularyBook.objects.all()
        context = {
            'vocabulary_books': vocabulary_books,
            'title': '准备导入单词到词汇书',
            'opts': self.model._meta,
        }
        return render(request, 'admin/vocabulary/bookword/import_words.html', context)

    # 添加导入按钮到管理界面
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_import_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(StudentCustomization)
class StudentCustomizationAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_word', 'created_at')
    list_filter = ('student',)
    search_fields = ('student__user__username', 'word_basic__word')
    readonly_fields = ('created_at',)
    
    def get_word(self, obj):
        return obj.word_basic.word
    get_word.short_description = '单词' 