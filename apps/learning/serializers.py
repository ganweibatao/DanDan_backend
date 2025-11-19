from rest_framework import serializers
from .models import LearningPlan, WordLearningStage
from apps.vocabulary.serializers import VocabularyBookSerializer, BookWordSerializer
from apps.accounts.serializers import TeacherSerializer, StudentSerializer
from apps.accounts.models import Student
from apps.vocabulary.models import BookWord



class LearningPlanSerializer(serializers.ModelSerializer):
    """学习计划序列化器"""
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
            'start_date', 'is_active', 'created_at', 'updated_at',
            'student_details', 'total_days', 'progress'
        ]
        read_only_fields = ['teacher', 'vocabulary_book', 'created_at', 'updated_at']

    def to_representation(self, instance):
        """自定义返回格式，优化返回数据"""
        rep = super().to_representation(instance)
        
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
        # 简化计算，不再依赖words_per_day
        if obj.vocabulary_book:
            word_count = obj.vocabulary_book.word_count or 0
            # 假设平均每天学习30个新单词
            return (word_count + 29) // 30  # Ceiling division
        return 0

    def get_progress(self, obj):
        # 基于单词学习阶段计算进度
        total_stages = WordLearningStage.objects.filter(learning_plan=obj).count()
        if total_stages == 0:
            return 0.0
        completed_stages = WordLearningStage.objects.filter(learning_plan=obj, current_stage=5).count()
        return round((completed_stages / total_stages) * 100, 2)


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
    nextReviewDate = serializers.DateField(source='next_review_date', read_only=True)
    stageHistory = serializers.SerializerMethodField()
    
    class Meta:
        model = WordLearningStage
        fields = [
            'bookWordId', 'word', 'meaning', 'phonetic', 'startDate', 
            'currentStage', 'nextReviewDate', 'stageHistory'
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