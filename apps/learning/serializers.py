from rest_framework import serializers
from .models import LearningPlan, LearningUnit, UnitReview
from apps.vocabulary.serializers import VocabularyBookSerializer, BookWordSerializer
from apps.accounts.serializers import TeacherSerializer, StudentSerializer
from apps.vocabulary.models import BookWord

class UnitReviewSerializer(serializers.ModelSerializer):
    """单元复习序列化器"""
    class Meta:
        model = UnitReview
        fields = [
            'id', 'learning_unit', 'review_date', 'review_order', 
            'is_completed', 'completed_at', 'created_at', 'updated_at'
        ]

class LearningUnitSerializer(serializers.ModelSerializer):
    """学习单元序列化器"""
    reviews = UnitReviewSerializer(many=True, read_only=True)
    words = BookWordSerializer(many=True, read_only=True, required=False)
    
    class Meta:
        model = LearningUnit
        fields = [
            'id', 'learning_plan', 'unit_number', 'start_word_order', 
            'end_word_order', 'expected_learn_date', 'is_learned', 
            'learned_at', 'created_at', 'updated_at', 'reviews',
            'words'
        ]

class LearningPlanSerializer(serializers.ModelSerializer):
    """学习计划序列化器"""
    units = LearningUnitSerializer(many=True, read_only=True)
    vocabulary_book = VocabularyBookSerializer(read_only=True)
    vocabulary_book_id = serializers.IntegerField(write_only=True, source='vocabulary_book')
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.IntegerField(write_only=True, source='teacher', required=False, allow_null=True)
    student_details = StudentSerializer(source='student', read_only=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=StudentSerializer.Meta.model.objects.all(), write_only=True, required=False
    )
    total_days = serializers.SerializerMethodField(read_only=True)
    progress = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = LearningPlan
        fields = [
            'id', 'student', 'teacher', 'teacher_id', 'vocabulary_book', 'vocabulary_book_id',
            'words_per_day', 'start_date', 'is_active', 'created_at', 'updated_at', 'units',
            'student_details', 'total_days', 'progress'
        ]
        read_only_fields = ['student', 'teacher', 'vocabulary_book', 'created_at', 'updated_at', 'units']

    def to_representation(self, instance):
        """自定义返回格式，优化返回数据"""
        rep = super().to_representation(instance)
        
        # 检查上下文，决定是否包含详细单元信息
        include_detailed_units = self.context.get('include_detailed_units', False)
        
        if not include_detailed_units and 'units' in rep and rep['units']:
            # 如果不要求详细单元，且存在单元数据，则进行汇总
            unit_count = len(rep['units'])
            learned_count = sum(1 for unit in rep['units'] if unit.get('is_learned', False)) # 使用 .get() 更安全
            rep['units_summary'] = {
                'total': unit_count,
                'learned': learned_count,
                'remaining': unit_count - learned_count
            }
            rep.pop('units') # 移除详细单元列表
        # 如果 include_detailed_units 为 True，则不执行任何操作，保留完整的 units 字段
        
        # 确保 teacher_id 不会出现在只读的表示中
        if 'teacher_id' in rep:
             rep.pop('teacher_id', None)

        # 确保 vocabulary_book_id 不会出现在只读的表示中
        if 'vocabulary_book_id' in rep:
             rep.pop('vocabulary_book_id', None)

        return rep 

    def get_total_days(self, obj):
        # Calculate total_days based on word_count and words_per_day
        if obj.vocabulary_book and obj.words_per_day > 0:
            word_count = obj.vocabulary_book.word_count or 0
            return (word_count + obj.words_per_day - 1) // obj.words_per_day # Ceiling division
        return 0

    def get_progress(self, obj):
        # Example progress calculation: percentage of learned units
        total_units = LearningUnit.objects.filter(learning_plan=obj).count()
        if total_units == 0:
            return 0.0
        learned_units = LearningUnit.objects.filter(learning_plan=obj, is_learned=True).count()
        return round((learned_units / total_units) * 100, 2) 