from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Max, Q
import csv
import io
from .models import (
    VocabularyBook, BookWord, WordBasic, StudentKnownWord
)


class CustomizedFilter(admin.SimpleListFilter):
    title = '自定义状态'
    parameter_name = 'customized'

    def lookups(self, request, model_admin):
        return (
            ('yes', '已自定义'),
            ('no', '未自定义'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(
                Q(custom_word__isnull=False) | 
                Q(custom_phonetic__isnull=False) | 
                Q(custom_meanings__isnull=False)
            ).exclude(
                Q(custom_word='') & 
                Q(custom_phonetic='') & 
                Q(custom_meanings__isnull=True)
            )
        elif self.value() == 'no':
            return queryset.filter(
                Q(custom_word__isnull=True) | Q(custom_word=''),
                Q(custom_phonetic__isnull=True) | Q(custom_phonetic=''),
                Q(custom_meanings__isnull=True)
            )
        return queryset

@admin.register(WordBasic)
class WordBasicAdmin(admin.ModelAdmin):
    list_display = ('word', 'phonetic_symbol', 'created_at', 'updated_at')
    search_fields = ('word', 'phonetic_symbol')
    readonly_fields = ('created_at', 'updated_at')

class BookWordInline(admin.TabularInline):
    model = BookWord
    extra = 0  # 不显示额外的空白表单
    fields = ('get_word_display', 'word_order', 'get_meanings_display')
    readonly_fields = ('get_word_display', 'word_order', 'get_meanings_display')  # 设为只读，避免意外修改
    max_num = 20  # 最多显示20个单词
    can_delete = False  # 禁止在此处删除单词
    show_change_link = True  # 显示"更改"链接，可以跳转到单词详情页面
    verbose_name = "单词预览"
    verbose_name_plural = "单词预览（仅显示前20个）"
    
    def get_queryset(self, request):
        """限制查询集，只显示前20个单词，按word_order排序"""
        qs = super().get_queryset(request)
        # 不能在这里使用切片，因为Django admin会在后面继续过滤
        return qs.select_related('word_basic').order_by('word_order')
    
    def get_max_num(self, request, obj=None, **kwargs):
        """动态设置最大显示数量"""
        return 20
    
    def get_word_display(self, obj):
        """显示有效单词"""
        return obj.effective_word
    get_word_display.short_description = '单词'
    
    def get_meanings_display(self, obj):
        """显示释义的简化版本"""
        if obj.meanings:
            # 只显示前2个释义，避免内容过长
            meanings_list = obj.meanings[:2] if isinstance(obj.meanings, list) else []
            if meanings_list:
                return '; '.join([f"{m.get('part_of_speech', '')} {', '.join(m.get('chinese_meanings', [])[:2])}" for m in meanings_list])
        return obj.custom_meanings or '-'
    get_meanings_display.short_description = '释义（部分）'

@admin.register(VocabularyBook)
class VocabularyBookAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'word_count', 'is_system_preset', 'created_at', 'updated_at')
    list_filter = ('is_system_preset',)
    search_fields = ('name', 'id')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'view_all_words_link')
    # 移除内联显示，提升页面加载速度
    # inlines = [BookWordInline]
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'word_count', 'is_system_preset')
        }),
        ('单词管理', {
            'fields': ('view_all_words_link',),
            'description': '此书籍不在详情页面显示单词列表以提升加载速度。点击下方按钮查看和管理此书籍的所有单词。'
        }),
        ('系统信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def view_all_words_link(self, obj):
        """显示查看所有单词的链接"""
        if obj and obj.pk:
            url = f'/admin/vocabulary/bookword/?vocabulary_book__id__exact={obj.pk}'
            return format_html('<a href="{}" target="_blank" class="button">查看所有单词 ({}个)</a>', url, obj.word_count)
        return '-'
    view_all_words_link.short_description = '单词管理'
    
    # 移除get_form方法，因为不再需要内联显示提示
    
    def delete_model(self, request, obj):
        """优化单个书籍删除性能"""
        from django.db import transaction, connection
        from apps.learning.models import LearningPlan, WordLearningStage
        import time
        
        start_time = time.time()
        
        with transaction.atomic():
            # 使用原生SQL批量删除，避免ORM的逐条删除 - 使用PostgreSQL兼容的语法
            with connection.cursor() as cursor:
                # 1. 删除单词学习阶段（通过学习计划关联）
                cursor.execute("""
                    DELETE FROM word_learning_stages 
                    WHERE learning_plan_id IN (
                        SELECT id FROM learning_plans WHERE vocabulary_book_id = %s
                    )
                """, [obj.id])
                stages_deleted = cursor.rowcount
                
                # 2. 删除学习计划
                cursor.execute("""
                    DELETE FROM learning_plans WHERE vocabulary_book_id = %s
                """, [obj.id])
                plans_deleted = cursor.rowcount
                
                # 3. 删除书籍单词
                cursor.execute("""
                    DELETE FROM book_words WHERE vocabulary_book_id = %s
                """, [obj.id])
                words_deleted = cursor.rowcount
                
                # 4. 删除书籍本身
                cursor.execute("""
                    DELETE FROM vocabulary_books WHERE id = %s
                """, [obj.id])
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.message_user(
            request, 
            f"成功删除书籍 '{obj.name}' 及其相关数据！"
            f"删除了 {words_deleted} 个单词，{plans_deleted} 个学习计划，{stages_deleted} 个学习阶段。"
            f"耗时: {duration:.2f} 秒",
            level=messages.SUCCESS
        )
    
    def delete_queryset(self, request, queryset):
        """优化批量删除性能"""
        from django.db import transaction, connection
        import time
        
        start_time = time.time()
        book_names = [book.name for book in queryset]
        book_ids = [book.id for book in queryset]
        
        with transaction.atomic():
            with connection.cursor() as cursor:
                # 批量删除所有相关数据 - 使用PostgreSQL兼容的语法
                cursor.execute("""
                    DELETE FROM word_learning_stages 
                    WHERE learning_plan_id IN (
                        SELECT id FROM learning_plans WHERE vocabulary_book_id IN %s
                    )
                """, [tuple(book_ids)])
                stages_deleted = cursor.rowcount
                
                cursor.execute("""
                    DELETE FROM learning_plans WHERE vocabulary_book_id IN %s
                """, [tuple(book_ids)])
                plans_deleted = cursor.rowcount
                
                cursor.execute("""
                    DELETE FROM book_words WHERE vocabulary_book_id IN %s
                """, [tuple(book_ids)])
                words_deleted = cursor.rowcount
                
                cursor.execute("""
                    DELETE FROM vocabulary_books WHERE id IN %s
                """, [tuple(book_ids)])
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.message_user(
            request,
            f"成功批量删除 {len(queryset)} 本书籍：{', '.join(book_names)}！"
            f"删除了 {words_deleted} 个单词，{plans_deleted} 个学习计划，{stages_deleted} 个学习阶段。"
            f"耗时: {duration:.2f} 秒",
            level=messages.SUCCESS
        )

@admin.register(BookWord)
class BookWordAdmin(admin.ModelAdmin):
    list_display = ('get_word', 'get_book_info', 'word_order', 'is_customized')
    list_filter = ('vocabulary_book', CustomizedFilter)
    search_fields = ('word_basic__word', 'custom_word', 'example_sentence', 'vocabulary_book__id')
    ordering = ('vocabulary_book', 'word_order')
    readonly_fields = ('created_at', 'updated_at', 'is_customized')
    list_per_page = 50  # 每页显示50条记录，减少单页字段数量
    list_max_show_all = 200  # 限制"显示全部"的最大数量
    
    fieldsets = (
        ('基础信息', {
            'fields': ('vocabulary_book', 'word_basic', 'word_order')
        }),
        ('自定义字段', {
            'fields': ('custom_word', 'custom_phonetic', 'custom_meanings'),
            'description': '这些字段用于词汇书特定的自定义，会覆盖基础信息'
        }),
        ('其他信息', {
            'fields': ('meanings', 'example_sentence')
        }),
        ('系统信息', {
            'fields': ('is_customized', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_word(self, obj):
        return obj.effective_word
    get_word.short_description = '有效单词'
    
    def get_book_info(self, obj):
        """显示词汇书ID和名称"""
        if obj.vocabulary_book:
            return f"ID:{obj.vocabulary_book.id} - {obj.vocabulary_book.name}"
        return "未关联词汇书"
    get_book_info.short_description = '词汇书 (ID-名称)'
    
    def is_customized(self, obj):
        return obj.is_customized
    is_customized.boolean = True
    is_customized.short_description = '已自定义'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-words/', self.admin_site.admin_view(self.import_book_words_view), name='vocabulary_bookword_import-book-words'),
            path('confirm-import/', self.admin_site.admin_view(self.confirm_import_view), name='vocabulary_bookword_confirm-import'),
            path('process-import/', self.admin_site.admin_view(self.process_import_view), name='vocabulary_bookword_process-import'),
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
                
                # 预处理数据以检查重复单词
                rows = list(reader)
                word_list = [row.get('word', '').strip() for row in rows if 'word' in row]
                duplicates = set([word for word in word_list if word_list.count(word) > 1])
                
                if duplicates:
                    duplicate_words = ', '.join(duplicates)
                    # 不再自动拒绝导入，而是记录下来作为警告
                    duplicate_warning = f"CSV文件中存在重复单词: {duplicate_words}。这些单词将作为独立记录导入。"
                    # 在会话中保存这个警告，以便在确认页面显示
                    request.session['duplicate_warning'] = duplicate_warning
                    # 在会话中保存当前的导入状态
                    import_data = {
                        'book_id': book_id,
                        'csv_content': decoded_file
                    }
                    request.session['import_data'] = import_data
                    # 重定向到确认页面
                    return redirect('admin:vocabulary_bookword_confirm-import')
                
                # 检查这些单词是否已经存在于当前词汇书中
                existing_words = []
                for word in word_list:
                    word_basic = WordBasic.objects.filter(word=word).first()
                    if word_basic and BookWord.objects.filter(vocabulary_book=book, word_basic=word_basic).exists():
                        existing_words.append(word)
                
                if existing_words:
                    # 不再自动更新，而是提示用户确认
                    existing_warning = f"以下单词已存在于词汇书中: {', '.join(existing_words)}。这些单词将作为新记录导入。"
                    # 在会话中保存这个警告
                    request.session['existing_warning'] = existing_warning
                    # 在会话中保存当前的导入状态
                    import_data = {
                        'book_id': book_id,
                        'csv_content': decoded_file
                    }
                    request.session['import_data'] = import_data
                    # 重定向到确认页面
                    return redirect('admin:vocabulary_bookword_confirm-import')
                
                word_count = 0
                # 获取当前词汇书中最大的word_order
                max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                    Max('word_order')
                ).get('word_order__max') or 0
                
                for row in rows:
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
                    
                    # 获取已存在的单词记录
                    existing_word = BookWord.objects.filter(
                        vocabulary_book=book,
                        word_basic=word_basic
                    ).first()
                    
                    # 初始化词义列表
                    if existing_word:
                        meanings = existing_word.meanings or []
                    else:
                        meanings = []
                    
                    # 处理可能的多个词性和释义（用分号分隔）
                    if part_of_speech and chinese_meaning:
                        pos_list = [pos.strip() for pos in part_of_speech.split(';') if pos.strip()]
                        
                        # 检查是否有使用方括号标记的复合释义 [释义1,释义2]
                        has_complex_meanings = '[' in chinese_meaning and ']' in chinese_meaning
                        
                        if has_complex_meanings:
                            # 复杂模式：支持一个词性对应多个释义
                            # 解析格式为: "普通释义;[复合释义1,复合释义2];普通释义"
                            raw_meanings = []
                            current_pos = 0
                            in_brackets = False
                            temp_meaning = ""
                            
                            # 解析复杂的释义格式
                            for char in chinese_meaning:
                                if char == '[':
                                    in_brackets = True
                                    temp_meaning += char
                                elif char == ']':
                                    in_brackets = False
                                    temp_meaning += char
                                elif char == ';' and not in_brackets:
                                    raw_meanings.append(temp_meaning.strip())
                                    temp_meaning = ""
                                else:
                                    temp_meaning += char
                            
                            # 添加最后一个释义
                            if temp_meaning:
                                raw_meanings.append(temp_meaning.strip())
                            
                            # 确保解析后的释义数量与词性数量匹配
                            if len(raw_meanings) == len(pos_list):
                                for i in range(len(pos_list)):
                                    pos = pos_list[i]
                                    raw_meaning = raw_meanings[i]
                                    
                                    # 检查是否是复合释义 [释义1,释义2]
                                    if raw_meaning.startswith('[') and raw_meaning.endswith(']'):
                                        # 提取方括号中的多个释义
                                        compound_meanings = raw_meaning[1:-1].split(',')
                                        final_meaning = '; '.join([m.strip() for m in compound_meanings])
                                    else:
                                        final_meaning = raw_meaning
                                    
                                    new_meaning = {'pos': pos, 'meaning': final_meaning}
                                    
                                    # 更新或添加释义
                                    pos_exists = False
                                    for j, meaning in enumerate(meanings):
                                        if meaning.get('pos') == new_meaning['pos']:
                                            meanings[j]['meaning'] = new_meaning['meaning']
                                            pos_exists = True
                                            break
                                    
                                    if not pos_exists:
                                        meanings.append(new_meaning)
                            else:
                                # 如果解析后的释义数量与词性数量不匹配，回退到简单处理
                                raise Exception(f"词性数量({len(pos_list)})与解析后的释义数量({len(raw_meanings)})不匹配")
                        else:
                            # 简单模式：使用分号分隔的普通释义
                            meaning_list = [mean.strip() for mean in chinese_meaning.split(';') if mean.strip()]
                            
                            # 确保词性和释义列表长度匹配
                            if len(pos_list) == len(meaning_list):
                                for i in range(len(pos_list)):
                                    new_meaning = {'pos': pos_list[i], 'meaning': meaning_list[i]}
                                    
                                    # 检查是否已存在相同词性
                                    pos_exists = False
                                    for j, meaning in enumerate(meanings):
                                        if meaning.get('pos') == new_meaning['pos']:
                                            # 更新已存在词性的释义
                                            meanings[j]['meaning'] = new_meaning['meaning']
                                            pos_exists = True
                                            break
                                    
                                    # 如果不存在该词性，添加新的词性和释义
                                    if not pos_exists:
                                        meanings.append(new_meaning)
                            elif len(pos_list) > 1 and len(meaning_list) == 1:
                                # 如果有多个词性但只有一个释义，将同一个释义应用到所有词性
                                for pos in pos_list:
                                    new_meaning = {'pos': pos, 'meaning': meaning_list[0]}
                                    
                                    # 检查是否已存在相同词性
                                    pos_exists = False
                                    for j, meaning in enumerate(meanings):
                                        if meaning.get('pos') == new_meaning['pos']:
                                            meanings[j]['meaning'] = new_meaning['meaning']
                                            pos_exists = True
                                            break
                                    
                                    if not pos_exists:
                                        meanings.append(new_meaning)
                            elif len(pos_list) == 1 and len(meaning_list) > 0:
                                # 如果只有一个词性但有多个释义，将所有释义合并
                                combined_meaning = '; '.join(meaning_list)
                                new_meaning = {'pos': pos_list[0], 'meaning': combined_meaning}
                                
                                # 更新或添加这个词性的释义
                                pos_exists = False
                                for j, meaning in enumerate(meanings):
                                    if meaning.get('pos') == new_meaning['pos']:
                                        meanings[j]['meaning'] = new_meaning['meaning']
                                        pos_exists = True
                                        break
                                
                                if not pos_exists:
                                    meanings.append(new_meaning)
                            else:
                                # 添加单个词性和释义
                                new_meaning = {'pos': part_of_speech, 'meaning': chinese_meaning}
                                
                                # 检查是否已存在相同词性
                                pos_exists = False
                                for j, meaning in enumerate(meanings):
                                    if meaning.get('pos') == new_meaning['pos']:
                                        meanings[j]['meaning'] = new_meaning['meaning']
                                        pos_exists = True
                                        break
                                
                                if not pos_exists:
                                    meanings.append(new_meaning)
                    
                    # 更新或创建单词记录
                    word, created = BookWord.objects.update_or_create(
                        vocabulary_book=book,
                        word_basic=word_basic,
                        defaults={
                            'word_order': max_order,  # 总是使用当前的max_order确保顺序连贯
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

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_import_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def confirm_import_view(self, request):
        """确认导入视图，显示警告并询问用户是否继续"""
        context = {
            'title': '确认导入单词',
            'opts': self.model._meta,
            'duplicate_warning': request.session.get('duplicate_warning', None),
            'existing_warning': request.session.get('existing_warning', None),
        }
        return render(request, 'admin/vocabulary/bookword/confirm_import.html', context)
        
    def process_import_view(self, request):
        """处理确认后的导入"""
        if request.method != 'POST':
            return redirect('admin:vocabulary_bookword_changelist')
            
        # 从会话中获取导入数据
        import_data = request.session.get('import_data', None)
        if not import_data:
            self.message_user(request, "导入会话已过期，请重新上传文件。", level=messages.ERROR)
            return redirect('admin:vocabulary_bookword_changelist')
            
        book_id = import_data.get('book_id')
        csv_content = import_data.get('csv_content')
        
        try:
            book = VocabularyBook.objects.get(id=book_id)
            io_string = io.StringIO(csv_content)
            reader = csv.DictReader(io_string)
            rows = list(reader)
            
            word_count = 0
            # 获取当前词汇书中最大的word_order
            max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                Max('word_order')
            ).get('word_order__max') or 0
            
            for row in rows:
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
                
                # 创建新单词记录，即使单词在该书中已存在
                max_order += 1
                
                # 处理词性和释义，转换为JSON格式
                part_of_speech = row.get('part_of_speech', '')
                chinese_meaning = row.get('chinese_meaning', '')
                
                # 处理复合释义格式
                meanings = []
                if part_of_speech and chinese_meaning:
                    # 这里可以保留之前复合释义的处理逻辑
                    # 但我们简化为基本处理，因为现在每个导入的单词都是独立记录
                    pos_list = [pos.strip() for pos in part_of_speech.split(';') if pos.strip()]
                    meaning_list = [mean.strip() for mean in chinese_meaning.split(';') if mean.strip()]
                    
                    if len(pos_list) == len(meaning_list):
                        for i in range(len(pos_list)):
                            meanings.append({'pos': pos_list[i], 'meaning': meaning_list[i]})
                    elif len(pos_list) > 0 and len(meaning_list) == 1:
                        for pos in pos_list:
                            meanings.append({'pos': pos, 'meaning': meaning_list[0]})
                    else:
                        meanings = [{'pos': part_of_speech, 'meaning': chinese_meaning}]
                
                # 创建新的单词记录，不检查是否已存在
                word = BookWord.objects.create(
                    vocabulary_book=book,
                    word_basic=word_basic,
                    word_order=max_order,
                    meanings=meanings,
                    example_sentence=row.get('example_sentence', '')
                )
                word_count += 1
            
            # 更新词汇书的词汇量
            total_words = BookWord.objects.filter(vocabulary_book=book).count()
            book.word_count = total_words
            book.save()
            
            # 清除会话中的导入数据
            if 'import_data' in request.session:
                del request.session['import_data']
            if 'duplicate_warning' in request.session:
                del request.session['duplicate_warning']
            if 'existing_warning' in request.session:
                del request.session['existing_warning']
            
            self.message_user(request, f"成功导入 {word_count} 个单词到词汇书 '{book.name}'")
            return redirect('admin:vocabulary_bookword_changelist')
        except Exception as e:
            self.message_user(request, f"导入失败: {str(e)}", level=messages.ERROR)
            return redirect('admin:vocabulary_bookword_changelist')



@admin.register(StudentKnownWord)
class StudentKnownWordAdmin(admin.ModelAdmin):
    list_display = ('student', 'get_word', 'marked_at')
    list_filter = ('student', 'marked_at')
    search_fields = ('student__user__username', 'word__word')
    readonly_fields = ('marked_at',)
    
    def get_word(self, obj):
        """返回关联单词的拼写"""
        return obj.word.word if obj.word else "未知单词"
    get_word.short_description = '单词' 