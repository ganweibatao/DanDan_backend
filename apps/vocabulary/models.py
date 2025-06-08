from django.db import models
from django.contrib.auth.models import User
from apps.accounts.models import Student

class VocabularyBook(models.Model):
    """词汇书籍表"""
    name = models.CharField(max_length=100, default='新词汇书', verbose_name='书名')
    word_count = models.IntegerField(default=0, verbose_name='词汇量')
    is_system_preset = models.BooleanField(default=False, verbose_name='是否为系统预设书籍')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '书籍'
        verbose_name_plural = '书籍'
        db_table = 'vocabulary_books'
    
    def __str__(self):
        return self.name

class WordBasic(models.Model):
    """单词基本信息表"""
    word = models.CharField(max_length=100, unique=True, verbose_name='单词拼写')
    phonetic_symbol = models.CharField(max_length=100, blank=True, null=True, verbose_name='音标')
    uk_pronunciation = models.URLField(blank=True, null=True, verbose_name='英式发音URL')
    us_pronunciation = models.URLField(blank=True, null=True, verbose_name='美式发音URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '单词基本信息'
        verbose_name_plural = '单词基本信息'
        db_table = 'word_basics'
        indexes = [
            models.Index(fields=['word'], name='idx_word')
        ]
    
    def __str__(self):
        return self.word

class BookWord(models.Model):
    """书籍单词表"""
    vocabulary_book = models.ForeignKey(
        VocabularyBook, 
        on_delete=models.CASCADE, 
        related_name='words',
        verbose_name='关联的词汇书',
        null=True,  # 允许为空，以便迁移
        blank=True  # 允许为空，以便迁移
    )
    word_basic = models.ForeignKey(
        WordBasic,
        on_delete=models.CASCADE,
        related_name='book_words',
        verbose_name='关联的单词基本信息',
        null=True,  # 允许为空，以便迁移
        blank=True  # 允许为空，以便迁移
    )
    word_order = models.IntegerField(default=0, verbose_name='单词在书中的顺序')
    meanings = models.JSONField(verbose_name='词性及中文释义JSON', default=list)
    example_sentence = models.TextField(blank=True, null=True, verbose_name='例句')
    
    # 新增自定义字段：用于词汇书特定的单词修改
    custom_word = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name='自定义单词拼写'
    )
    custom_phonetic = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        verbose_name='自定义音标'
    )
    custom_meanings = models.JSONField(
        blank=True, 
        null=True,
        verbose_name='自定义释义（覆盖基础释义）'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '书籍单词'
        verbose_name_plural = '书籍单词'
        db_table = 'book_words'
        indexes = [
            models.Index(fields=['vocabulary_book', 'word_order'], name='idx_book_order')
        ]
    
    # 优先级属性：自定义字段优先于基础字段
    @property
    def effective_word(self):
        """获取有效的单词拼写：自定义 > 基础"""
        return self.custom_word or (self.word_basic.word if self.word_basic else "Unknown Word")
    
    @property  
    def effective_phonetic(self):
        """获取有效的音标：自定义 > 基础"""
        return self.custom_phonetic or (self.word_basic.phonetic_symbol if self.word_basic else None)
    
    @property
    def effective_meanings(self):
        """获取有效的释义：自定义 > 基础"""
        return self.custom_meanings or self.meanings
    
    @property
    def is_customized(self):
        """判断是否被自定义过"""
        return bool(self.custom_word or self.custom_phonetic or self.custom_meanings)
        
    def __str__(self):
        return self.effective_word



class StudentKnownWord(models.Model):
    """学生已认识单词表"""
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='known_words_set', 
        verbose_name="学生"
    )
    word = models.ForeignKey(
        WordBasic, 
        on_delete=models.CASCADE, 
        related_name='known_by_students', 
        verbose_name="单词"
    )
    marked_at = models.DateTimeField(auto_now_add=True, verbose_name="标记时间")

    class Meta:
        verbose_name = "学生已认识单词"
        verbose_name_plural = verbose_name
        db_table = 'vocabulary_studentknownword' # 明确表名
        unique_together = ('student', 'word')
        ordering = ['-marked_at']
        indexes = [
            models.Index(fields=['student', 'word'], name='idx_student_known_word'),
        ]

    def __str__(self):
        return f"{self.student.user.username} knows {self.word.word}"