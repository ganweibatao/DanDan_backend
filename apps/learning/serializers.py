from rest_framework import serializers
from .models import LearningPlan, LearningUnit, UnitReview, WordLearningStage
from apps.vocabulary.serializers import VocabularyBookSerializer, BookWordSerializer
from apps.accounts.serializers import TeacherSerializer, StudentSerializer
from apps.accounts.models import Student
from apps.vocabulary.models import BookWord

class UnitReviewSerializer(serializers.ModelSerializer):
    """单元复习序列化器"""
    class Meta:
        model = UnitReview
        fields = [
            'id', 'learning_unit', 'review_date', 'review_order', 
            'is_completed', 'completed_at', 'created_at', 'updated_at'
        ]

# 为矩阵视图添加精简版复习序列化器
class EbinghausReviewSerializer(serializers.ModelSerializer):
    """艾宾浩斯矩阵专用的精简复习序列化器"""
    class Meta:
        model = UnitReview
        fields = ['id', 'review_order', 'is_completed']

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

# 为矩阵视图添加精简版学习单元序列化器
class EbinghausUnitSerializer(serializers.ModelSerializer):
    """艾宾浩斯矩阵专用的精简学习单元序列化器"""
    reviews = EbinghausReviewSerializer(many=True, read_only=True)
    
    class Meta:
        model = LearningUnit
        fields = [
            'id', 'unit_number', 'start_word_order', 'end_word_order',
            'is_learned', 'learned_at', 'reviews'
        ]

class LearningPlanSerializer(serializers.ModelSerializer):
    """学习计划序列化器"""
    units = LearningUnitSerializer(many=True, read_only=True)
    vocabulary_book = VocabularyBookSerializer(read_only=True)
    vocabulary_book_id = serializers.IntegerField(write_only=True)
    teacher = TeacherSerializer(read_only=True)
    teacher_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    student_details = StudentSerializer(source='student', read_only=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), write_only=True, required=False
    )
    student_id = serializers.IntegerField(write_only=True, required=False)
    total_days = serializers.SerializerMethodField(read_only=True)
    progress = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = LearningPlan
        fields = [
            'id', 'student', 'student_id', 'teacher', 'teacher_id', 'vocabulary_book', 'vocabulary_book_id',
            'words_per_day', 'start_date', 'is_active', 'created_at', 'updated_at', 'units',
            'student_details', 'total_days', 'progress'
        ]
        read_only_fields = ['teacher', 'vocabulary_book', 'created_at', 'updated_at', 'units']

    def to_representation(self, instance):
        """自定义返回格式，优化返回数据"""
        rep = super().to_representation(instance)
        
        # 检查上下文，决定是否包含详细单元信息
        include_detailed_units = self.context.get('include_detailed_units', False)
        is_for_matrix = self.context.get('is_for_matrix', False)
        
        if is_for_matrix:
            # 如果是为矩阵视图优化，使用精简的单元序列化器
            units = instance.units
            # 兼容 manager/list
            if hasattr(units, 'all'):
                units = units.all()
            rep['units'] = EbinghausUnitSerializer(units, many=True).data
        elif not include_detailed_units and 'units' in rep and rep['units']:
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

        # 确保 student_id 不会出现在只读的表示中
        if 'student_id' in rep:
             rep.pop('student_id', None)

        return rep 

    def create(self, validated_data):
        """自定义创建方法，处理 vocabulary_book_id、teacher_id 和 student_id"""
        vocabulary_book_id = validated_data.pop('vocabulary_book_id', None)
        teacher_id = validated_data.pop('teacher_id', None)
        student_id = validated_data.pop('student_id', None)
        
        if vocabulary_book_id:
            from apps.vocabulary.models import VocabularyBook
            validated_data['vocabulary_book'] = VocabularyBook.objects.get(id=vocabulary_book_id)
            
        if teacher_id:
            from apps.accounts.models import Teacher
            validated_data['teacher'] = Teacher.objects.get(id=teacher_id)
            
        if student_id:
            validated_data['student'] = Student.objects.get(id=student_id)
            
        return super().create(validated_data)

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


class WordStageHistorySerializer(serializers.Serializer):
    """单词学习阶段历史记录序列化器"""
    stage = serializers.IntegerField()
    completed_at = serializers.DateTimeField()


class WordStageSerializer(serializers.ModelSerializer):
    """单词学习阶段序列化器 - 用于前端 DuolingoStudyPlan 组件"""
    bookWordId = serializers.IntegerField(source='book_word.id', read_only=True)
    word = serializers.CharField(source='book_word.effective_word', read_only=True)
    meaning = serializers.JSONField(source='book_word.effective_meanings', read_only=True)
    phonetic = serializers.CharField(source='book_word.effective_phonetic', read_only=True)
    startDate = serializers.DateField(source='start_date', read_only=True)
    currentStage = serializers.IntegerField(source='current_stage', read_only=True)
    stageHistory = serializers.SerializerMethodField()
    
    class Meta:
        model = WordLearningStage
        fields = [
            'bookWordId', 'word', 'meaning', 'phonetic', 'startDate', 
            'currentStage', 'stageHistory'
        ]
    
    def get_stageHistory(self, obj):
        """构建阶段历史记录"""
        history = []
        
        # 添加起始阶段 (stage 0)
        if obj.start_date:
            history.append({
                'stage': 0,
                'completedAt': obj.start_date.isoformat()
            })
        
        # 如果当前阶段大于 0，则添加后续阶段的历史
        # 这里需要根据实际的复习记录来构建，暂时简化处理
        current_date = obj.start_date
        for stage in range(1, obj.current_stage + 1):
            if stage < len(obj.STAGE_INTERVALS):
                # 根据间隔计算完成日期
                from datetime import timedelta
                interval_days = obj.STAGE_INTERVALS[stage-1] if stage > 0 else 0
                current_date = current_date + timedelta(days=interval_days)
                history.append({
                    'stage': stage,
                    'completedAt': current_date.isoformat()
                })
        
        return history


class WordLearningStageSerializer(serializers.ModelSerializer):
    """完整的单词学习阶段序列化器"""
    book_word = BookWordSerializer(read_only=True)
    book_word_id = serializers.IntegerField(write_only=True, source='book_word')
    
    class Meta:
        model = WordLearningStage
        fields = [
            'id', 'learning_plan', 'book_word', 'book_word_id', 'current_stage',
            'start_date', 'last_reviewed_at', 'next_review_date',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']