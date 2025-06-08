from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from apps.vocabulary.models import VocabularyBook, BookWord
from apps.accounts.models import Student, Teacher

class LearningPlan(models.Model):
    """学习计划表"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='learning_plans')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_learning_plans', verbose_name='负责老师')
    vocabulary_book = models.ForeignKey(VocabularyBook, on_delete=models.CASCADE, related_name='learning_plans')
    words_per_day = models.IntegerField(verbose_name='每日新单词量')
    start_date = models.DateField(verbose_name='计划开始日期')
    is_active = models.BooleanField(default=False, verbose_name='是否为当前正在学习的计划')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '学习计划'
        verbose_name_plural = '学习计划'
        db_table = 'learning_plans'
        indexes = [
            models.Index(fields=['student', 'vocabulary_book'], name='idx_student_book'),
            models.Index(fields=['student', 'is_active'], name='idx_student_active'),
            models.Index(fields=['teacher'], name='idx_teacher'),
        ]
    
    def __str__(self):
        teacher_info = f" supervised by {self.teacher.user.username}" if self.teacher else ""
        return f"{self.student.user.username}'s plan for {self.vocabulary_book.name}{teacher_info}"

class LearningUnit(models.Model):
    """学习单元表"""
    learning_plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE, related_name='units')
    unit_number = models.IntegerField()
    start_word_order = models.IntegerField()
    end_word_order = models.IntegerField()
    expected_learn_date = models.DateField()
    is_learned = models.BooleanField(default=False)
    learned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '学习单元'
        verbose_name_plural = '学习单元'
        db_table = 'learning_units'
        indexes = [
            models.Index(fields=['learning_plan', 'unit_number'], name='idx_plan_unit'),
            models.Index(fields=['expected_learn_date'], name='idx_learn_date')
        ]
    
    def __str__(self):
        return f"Unit {self.unit_number} of {self.learning_plan}"

class UnitReview(models.Model):
    """单元复习记录表"""
    learning_unit = models.ForeignKey(LearningUnit, on_delete=models.CASCADE, related_name='reviews')
    review_date = models.DateField(verbose_name='艾宾浩斯计划复习日期')
    review_order = models.IntegerField(verbose_name='第几次复习(1-5)')
    is_completed = models.BooleanField(default=False, verbose_name='是否已完成')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = '单元复习记录'
        verbose_name_plural = '单元复习记录'
        db_table = 'unit_reviews'
        unique_together = ['learning_unit', 'review_order']
        indexes = [
            models.Index(fields=['review_date'], name='idx_review_date')
        ]
    
    def __str__(self):
        return f"Review {self.review_order} of {self.learning_unit}"


class WordLearningStage(models.Model):
    """单词学习阶段表 - 基于艾宾浩斯遗忘曲线的单词学习进度"""
    learning_plan = models.ForeignKey(LearningPlan, on_delete=models.CASCADE, related_name='word_stages')
    book_word = models.ForeignKey(BookWord, on_delete=models.CASCADE, related_name='learning_stages')
    current_stage = models.IntegerField(default=0, verbose_name='当前学习阶段(0-5)')
    start_date = models.DateField(verbose_name='首次学习日期')
    last_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='最后复习时间')
    next_review_date = models.DateField(null=True, blank=True, verbose_name='下次复习日期')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 艾宾浩斯间隔天数：stage 0(新学) -> 1(1天后) -> 2(1天后) -> 3(2天后) -> 4(3天后) -> 5(7天后) -> 完成
    STAGE_INTERVALS = [0, 1, 1, 2, 3, 7]
    
    class Meta:
        verbose_name = '单词学习阶段'
        verbose_name_plural = '单词学习阶段'
        db_table = 'word_learning_stages'
        unique_together = ['learning_plan', 'book_word']
        indexes = [
            models.Index(fields=['learning_plan', 'current_stage'], name='idx_plan_stage'),
            models.Index(fields=['next_review_date'], name='idx_next_review'),
            models.Index(fields=['learning_plan', 'next_review_date'], name='idx_plan_review_date'),
        ]
    
    def __str__(self):
        return f"{self.book_word.word_basic.word if self.book_word.word_basic else 'Unknown Word'} - Stage {self.current_stage} in {self.learning_plan}"
    
    def advance_stage(self):
        """将单词推进到下一个学习阶段"""
        if self.current_stage < 5:
            self.current_stage += 1
            self.last_reviewed_at = timezone.now()
            
            if self.current_stage < len(self.STAGE_INTERVALS):
                # 计算下次复习日期
                interval_days = self.STAGE_INTERVALS[self.current_stage]
                self.next_review_date = timezone.now().date() + timedelta(days=interval_days)
            else:
                # 已完成所有阶段
                self.next_review_date = None
            
            self.save()
            return True
        return False
    
    def is_ready_for_review(self, today=None):
        """检查单词是否已到复习时间"""
        if today is None:
            today = timezone.now().date()
        
        if self.current_stage == 0:
            # 新词总是可以学习
            return True
        
        if self.next_review_date is None:
            # 已完成所有阶段
            return False
        
        return today >= self.next_review_date
    
    @classmethod
    def create_for_plan(cls, learning_plan, book_words=None):
        """为学习计划创建单词学习阶段记录（批量创建优化）"""
        if book_words is None:
            book_words = learning_plan.vocabulary_book.words.all()
        
        start_date = learning_plan.start_date
        
        # 检查已存在的记录，避免重复创建
        existing_word_ids = set(
            cls.objects.filter(learning_plan=learning_plan)
            .values_list('book_word_id', flat=True)
        )
        
        # 准备批量创建的数据
        word_stages_to_create = []
        for book_word in book_words:
            if book_word.id not in existing_word_ids:
                word_stages_to_create.append(cls(
                    learning_plan=learning_plan,
                    book_word=book_word,
                    current_stage=0,
                    start_date=start_date,
                    next_review_date=start_date,  # 新词在开始日期就可以学习
                ))
        
        # 批量创建，提高性能
        if word_stages_to_create:
            created_stages = cls.objects.bulk_create(word_stages_to_create, batch_size=1000)
            print(f"批量创建了 {len(created_stages)} 个单词学习阶段记录")
            return created_stages
        
        return []