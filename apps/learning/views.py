from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
import threading
from django.db.models import Q, Prefetch
from datetime import timedelta
from .models import LearningPlan, WordLearningStage
from .serializers import (
    LearningPlanSerializer,
    WordLearningStageSerializer, WordStageSerializer
)
from apps.accounts.models import Student, Teacher
from apps.vocabulary.models import BookWord


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
        """获取词汇书中可用于学习的单词列表，并标记已有学习记录或学生已认识的单词。"""
        learning_plan = self.get_object()
        student = learning_plan.student

        # 获取分页参数
        limit = request.query_params.get('limit')
        offset = request.query_params.get('offset', '0')
        
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            offset = 0
            
        try:
            limit = int(limit) if limit is not None else None
        except (ValueError, TypeError):
            limit = None

        # 获取已创建学习阶段的单词ID
        existing_stage_word_ids = set(
            WordLearningStage.objects.filter(learning_plan=learning_plan)
            .values_list('book_word_id', flat=True)
        )
        
        # 获取学生已认识的单词的 WordBasic ID
        known_word_basic_ids = set()
        if student:
            from apps.vocabulary.models import StudentKnownWord
            known_word_basic_ids = set(
                StudentKnownWord.objects.filter(student=student)
                .values_list('word_id', flat=True)
            )

        # 获取词汇书中的所有单词（用于计算总数）
        from apps.vocabulary.models import BookWord
        all_words_query = BookWord.objects.filter(
            vocabulary_book=learning_plan.vocabulary_book
        ).select_related('word_basic').order_by('word_order', 'id')
        
        # 计算总数
        total_count = all_words_query.count()
        
        # 筛选出可用于学习的单词（没有学习记录且不是已知单词）
        available_words_query = all_words_query.exclude(
            id__in=existing_stage_word_ids  # 排除已有学习阶段记录的单词
        ).exclude(
            word_basic_id__in=known_word_basic_ids  # 排除学生已认识的单词
        )
        
        # 计算可用单词总数
        available_total_count = available_words_query.count()
        
        # 应用分页（只对可用单词分页）
        if limit is not None:
            words_to_process = available_words_query[offset:offset + limit]
        else:
            words_to_process = available_words_query[offset:] if offset > 0 else available_words_query
        
        # 构建返回数据（所有返回的单词都是可学习的）
        words_data = []
        for word in words_to_process:
            word_data = {
                'id': word.id,
                'word': word.effective_word,
                'meaning': word.effective_meanings,
                'phonetic': word.effective_phonetic,
                'word_order': word.word_order,
                'word_basic_id': word.word_basic.id if word.word_basic else None,  # 添加word_basic_id字段
                'has_stage': False,  # 筛选后的单词都没有学习记录
                'is_known': False    # 筛选后的单词都不是已知单词
            }
            words_data.append(word_data)
        
        known_in_book_count = BookWord.objects.filter(
            vocabulary_book=learning_plan.vocabulary_book, 
            word_basic_id__in=known_word_basic_ids
        ).count()

        return Response({
            'words': words_data,
            'total_count': available_total_count,  # 返回可用单词的总数，而不是所有单词的总数
            'all_words_count': total_count,  # 添加词书中所有单词的总数
            'staged_count': len(existing_stage_word_ids),
            'known_in_book_count': known_in_book_count,
        })
    
    @action(detail=True, methods=['get'])
    def words_stages(self, request, pk=None):
        """获取学习计划中所有单词的学习阶段信息，并自动将符合条件的stage 0单词推进到stage 1"""
        import logging
        import pytz
        logger = logging.getLogger('django')
        
        learning_plan = self.get_object()
        
        # 获取北京时间的今日日期，用于检查和更新
        beijing_tz = pytz.timezone('Asia/Shanghai')
        beijing_now = timezone.now().astimezone(beijing_tz)
        today = beijing_now.date()
        logger.info(f"words_stages 开始处理，学习计划ID: {learning_plan.id}, UTC时间: {timezone.now()}, 北京时间: {beijing_now}, 北京日期: {today}")
        
        # 自动推进stage 0到stage 1的逻辑
        with transaction.atomic():
            # 获取所有stage 0的单词
            stage_0_words = WordLearningStage.objects.filter(
                learning_plan=learning_plan,
                current_stage=0
            ).select_related('book_word')
            
            logger.info(f"找到 {stage_0_words.count()} 个stage 0的单词需要检查")
            
            updated_count = 0
            for word_stage in stage_0_words:
                # 详细日志记录每个单词的检查过程
                start_date = word_stage.start_date
                if start_date:
                    should_advance_date = start_date + timedelta(days=1)
                    should_advance = today >= should_advance_date
                    
                    if should_advance:
                        # 推进到stage 1
                        word_stage.current_stage = 1
                        word_stage.last_reviewed_at = timezone.now()
                        
                        # 计算下次复习日期 (stage 1间隔1天)
                        word_stage.next_review_date = today + timedelta(days=WordLearningStage.STAGE_INTERVALS[1])
                        word_stage.save()
                        
                        updated_count += 1
                    else:
                        logger.info(f"✗ 单词 '{word_stage.book_word.effective_word}' 暂不推进")
            
            if updated_count > 0:
                logger.info(f"自动推进了 {updated_count} 个单词从stage 0到stage 1")
            else:
                logger.info("没有单词需要推进")
        
        # 获取所有单词阶段（包括刚刚更新的）
        word_stages = WordLearningStage.objects.filter(
            learning_plan=learning_plan
        ).select_related('book_word').order_by('book_word__word_order', 'book_word__id')
        
        # 序列化数据
        serializer = WordStageSerializer(word_stages, many=True)
        
        response_data = serializer.data
        if updated_count > 0:
            # 在响应中添加更新信息
            return Response({
                'words': response_data,
                'auto_advanced': {
                    'count': updated_count,
                    'message': f'自动推进了 {updated_count} 个单词从新学阶段到第1轮复习'
                }
            })
        else:
            return Response(response_data)
    
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



 