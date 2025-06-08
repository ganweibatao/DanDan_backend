from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
import threading
from .models import LearningPlan, LearningUnit, UnitReview, WordLearningStage
from .serializers import (
    LearningPlanSerializer, LearningUnitSerializer, UnitReviewSerializer,
    WordStageSerializer, WordLearningStageSerializer
)
from apps.accounts.models import Student, Teacher


class LearningPlanViewSet(viewsets.ModelViewSet):
    """学习计划视图集"""
    serializer_class = LearningPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """根据用户类型返回不同的查询集"""
        import logging
        logger = logging.getLogger('django')
        
        user = self.request.user
        student_id = self.request.query_params.get('student_id')
        
        logger.info(f"LearningPlan get_queryset: 用户={user}, 用户ID={user.id}, student_id参数={student_id}")
        logger.info(f"用户角色检查: hasattr(user, 'student_profile')={hasattr(user, 'student_profile')}, hasattr(user, 'teacher_profile')={hasattr(user, 'teacher_profile')}")
        
        if hasattr(user, 'student_profile'):
            # 学生只能看到自己的学习计划
            queryset = LearningPlan.objects.filter(student=user.student_profile)
            logger.info(f"学生用户查询结果: {queryset.count()} 个学习计划")
            return queryset
        elif hasattr(user, 'teacher_profile'):
            # 教师可以查看：
            # 1. 自己创建的学习计划
            # 2. 自己管理的学生的学习计划（通过师生关系）
            # 3. 如果指定了学生ID，该学生的学习计划
            from apps.accounts.models import StudentTeacherRelationship
            
            teacher = user.teacher_profile
            logger.info(f"教师用户: teacher_id={teacher.id}, teacher_user={teacher.user}")
            
            if student_id:
                # 如果指定了学生ID，返回该学生的所有学习计划（不限制教师）
                queryset = LearningPlan.objects.filter(student_id=student_id)
                logger.info(f"指定学生ID={student_id}的查询结果: {queryset.count()} 个学习计划")
                for plan in queryset:
                    logger.info(f"  计划ID={plan.id}, 学生={plan.student}, 教师={plan.teacher}")
                return queryset
            
            # 获取教师管理的所有学生
            managed_student_ids = StudentTeacherRelationship.objects.filter(
                teacher=teacher
            ).values_list('student_id', flat=True)
            
            logger.info(f"教师管理的学生ID列表: {list(managed_student_ids)}")
            
            # 返回：自己创建的计划 + 管理学生的计划
            from django.db.models import Q
            queryset = LearningPlan.objects.filter(
                Q(teacher=teacher) | Q(student_id__in=managed_student_ids)
            )
            
            logger.info(f"教师最终查询结果: {queryset.count()} 个学习计划")
            for plan in queryset:
                logger.info(f"  计划ID={plan.id}, 学生={plan.student} (ID={plan.student.id}), 教师={plan.teacher}")
            
            return queryset
        else:
            # 超级用户或其他角色可以通过student_id查询
            logger.info(f"超级用户或其他角色")
            if student_id:
                queryset = LearningPlan.objects.filter(student_id=student_id)
                logger.info(f"超级用户指定学生ID={student_id}的查询结果: {queryset.count()} 个学习计划")
                return queryset
            return LearningPlan.objects.none()
    
    def perform_create(self, serializer):
        """创建学习计划时自动设置创建者，不再预先创建单词阶段"""
        user = self.request.user
        
        if hasattr(user, 'student'):
            # 学生创建自己的学习计划
            learning_plan = serializer.save(student=user.student)
        elif hasattr(user, 'teacher'):
            # 教师创建学习计划，需要指定学生
            student_id = self.request.data.get('student_id')
            if student_id:
                student = get_object_or_404(Student, id=student_id)
                learning_plan = serializer.save(teacher=user.teacher, student=student)
            else:
                learning_plan = serializer.save(teacher=user.teacher)
        else:
            learning_plan = serializer.save()
        
        # 注释：单词阶段记录将在用户实际选择单词学习时创建
    
    @action(detail=True, methods=['post'])
    def create_word_stages(self, request, pk=None):
        """为指定单词创建学习阶段记录"""
        import logging
        logger = logging.getLogger('django')
        
        logger.info(f"create_word_stages 开始: pk={pk}, 用户={request.user}, 用户ID={request.user.id}")
        logger.info(f"请求数据: {request.data}")
        
        try:
            logger.info(f"尝试获取学习计划对象 ID={pk}")
            learning_plan = self.get_object()
            logger.info(f"成功获取学习计划: {learning_plan}, 学生={learning_plan.student}, 教师={learning_plan.teacher}")
        except Exception as e:
            logger.error(f"获取学习计划失败: {str(e)}")
            logger.error(f"当前queryset包含的计划: {[plan.id for plan in self.get_queryset()]}")
            raise
        
        book_word_ids = request.data.get('book_word_ids', [])
        
        if not book_word_ids:
            return Response(
                {'error': '请提供要创建阶段记录的单词ID列表'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                from apps.vocabulary.models import BookWord
                
                # 获取指定的单词
                book_words = BookWord.objects.filter(
                    id__in=book_word_ids,
                    vocabulary_book=learning_plan.vocabulary_book
                )
                
                if not book_words.exists():
                    return Response(
                        {'error': '未找到有效的单词'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 创建单词学习阶段记录
                created_stages = WordLearningStage.create_for_plan(learning_plan, book_words)
                
                return Response({
                    'success': True,
                    'message': f'成功为 {len(created_stages)} 个单词创建学习阶段记录',
                    'created_count': len(created_stages),
                    'word_ids': [stage.book_word_id for stage in created_stages]
                })
        
        except Exception as e:
            return Response(
                {'error': f'创建单词阶段记录失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def available_words(self, request, pk=None):
        """获取词汇书中可用于学习的单词列表"""
        learning_plan = self.get_object()
        
        # 获取词汇书中的所有单词
        from apps.vocabulary.models import BookWord
        all_words = BookWord.objects.filter(
            vocabulary_book=learning_plan.vocabulary_book
        ).select_related('word_basic').order_by('order', 'id')
        
        # 获取已创建学习阶段的单词ID
        existing_stage_word_ids = set(
            WordLearningStage.objects.filter(learning_plan=learning_plan)
            .values_list('book_word_id', flat=True)
        )
        
        # 构建返回数据
        words_data = []
        for word in all_words:
            word_data = {
                'id': word.id,
                'word': word.word_basic.word if word.word_basic else 'Unknown',
                'translation': word.translation,
                'pronunciation': word.pronunciation,
                'order': word.order,
                'has_stage': word.id in existing_stage_word_ids
            }
            words_data.append(word_data)
        
        return Response({
            'words': words_data,
            'total_count': len(words_data),
            'staged_count': len(existing_stage_word_ids)
        })
    
    @action(detail=True, methods=['get'])
    def words_stages(self, request, pk=None):
        """获取学习计划中所有单词的学习阶段信息"""
        learning_plan = self.get_object()
        
        # 获取今天的日期，用于筛选可复习的单词
        today = timezone.now().date()
        
        # 获取所有单词阶段
        word_stages = WordLearningStage.objects.filter(
            learning_plan=learning_plan
        ).select_related('book_word').order_by('book_word__word_order', 'book_word__id')
        
        # 序列化数据
        serializer = WordStageSerializer(word_stages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def advance_word_stage(self, request, pk=None):
        """推进单词到下一个学习阶段"""
        learning_plan = self.get_object()
        book_word_id = request.data.get('book_word_id')
        
        if not book_word_id:
            return Response(
                {'error': '缺少 book_word_id 参数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            word_stage = WordLearningStage.objects.get(
                learning_plan=learning_plan,
                book_word_id=book_word_id
            )
            
            if word_stage.advance_stage():
                serializer = WordLearningStageSerializer(word_stage)
                return Response({
                    'success': True,
                    'message': f'单词 "{word_stage.book_word.word}" 已推进到阶段 {word_stage.current_stage}',
                    'word_stage': serializer.data
                })
            else:
                return Response({
                    'success': False,
                    'message': '单词已完成所有学习阶段'
                })
        
        except WordLearningStage.DoesNotExist:
            return Response(
                {'error': '未找到指定的单词学习记录'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], url_path='advance-stages-batch')
    def advance_word_stages_batch(self, request, pk=None):
        """批量推进单词到下一个学习阶段"""
        learning_plan = self.get_object()
        book_word_ids = request.data.get('book_word_ids', [])

        if not isinstance(book_word_ids, list) or not book_word_ids:
            return Response(
                {'error': 'book_word_ids 必须是一个包含ID的非空列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        advanced_stages = []
        failed_words = []

        word_stages = WordLearningStage.objects.filter(
            learning_plan=learning_plan,
            book_word_id__in=book_word_ids
        )

        with transaction.atomic():
            for stage in word_stages:
                if stage.advance_stage():
                    stage.save()
                    advanced_stages.append(stage)
                else:
                    failed_words.append({
                        'book_word_id': stage.book_word_id,
                        'reason': '已完成所有阶段或不满足推进条件'
                    })
        
        found_word_ids = {stage.book_word_id for stage in word_stages}
        not_found_ids = set(book_word_ids) - found_word_ids
        if not_found_ids:
            for word_id in not_found_ids:
                failed_words.append({
                    'book_word_id': word_id,
                    'reason': '未找到学习记录'
                })

        serializer = WordLearningStageSerializer(advanced_stages, many=True)
        return Response({
            'success': True,
            'message': f'成功推进 {len(advanced_stages)} 个单词，失败 {len(failed_words)} 个。',
            'advanced_stages': serializer.data,
            'failed_words': failed_words
        })


class LearningUnitViewSet(viewsets.ModelViewSet):
    """学习单元视图集"""
    serializer_class = LearningUnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """根据用户类型和学习计划过滤单元"""
        user = self.request.user
        learning_plan_id = self.request.query_params.get('learning_plan_id')
        
        base_queryset = LearningUnit.objects.all()
        
        if learning_plan_id:
            base_queryset = base_queryset.filter(learning_plan_id=learning_plan_id)
        
        if hasattr(user, 'student'):
            # 学生只能看到自己学习计划的单元
            return base_queryset.filter(learning_plan__student=user.student)
        elif hasattr(user, 'teacher'):
            # 教师只能看到自己创建的学习计划的单元
            return base_queryset.filter(learning_plan__teacher=user.teacher)
        else:
            return LearningUnit.objects.none()


class UnitReviewViewSet(viewsets.ModelViewSet):
    """单元复习视图集"""
    serializer_class = UnitReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """根据用户类型和学习单元过滤复习记录"""
        user = self.request.user
        learning_unit_id = self.request.query_params.get('learning_unit_id')
        
        base_queryset = UnitReview.objects.all()
        
        if learning_unit_id:
            base_queryset = base_queryset.filter(learning_unit_id=learning_unit_id)
        
        if hasattr(user, 'student'):
            # 学生只能看到自己学习计划的复习记录
            return base_queryset.filter(learning_unit__learning_plan__student=user.student)
        elif hasattr(user, 'teacher'):
            # 教师只能看到自己创建的学习计划的复习记录
            return base_queryset.filter(learning_unit__learning_plan__teacher=user.teacher)
        else:
            return UnitReview.objects.none()
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """标记复习为完成"""
        review = self.get_object()
        review.is_completed = True
        review.save()
        return Response({'status': 'completed'}) 