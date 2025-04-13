from django.db import models
from django.contrib.auth.models import User
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
    unit_number = models.IntegerField(verbose_name='单元序号')
    start_word_order = models.IntegerField(verbose_name='单元起始单词序号')
    end_word_order = models.IntegerField(verbose_name='单元结束单词序号')
    expected_learn_date = models.DateField(verbose_name='计划学习日期')
    is_learned = models.BooleanField(default=False, verbose_name='是否已学习')
    learned_at = models.DateTimeField(null=True, blank=True, verbose_name='完成学习时间')
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