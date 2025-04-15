from rest_framework import viewsets, permissions, filters, generics, status
from django_filters.rest_framework import DjangoFilterBackend
from .models import LearningPlan, LearningUnit, UnitReview
from .serializers import LearningPlanSerializer, LearningUnitSerializer, UnitReviewSerializer
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from apps.vocabulary.models import VocabularyBook, BookWord
from apps.accounts.models import Student, Teacher
from apps.accounts.permissions import IsTeacher, IsStudent, IsStudentOwnerOrRelatedTeacherOrAdmin, IsRelatedTeacherOrAdmin
import datetime
from datetime import timedelta
from django.db import transaction
import math # 导入 math 用于 ceil 计算
from apps.vocabulary.serializers import VocabularyBookSerializer, BookWordSerializer

# 艾宾浩斯复习间隔定义 (单位: 天)
EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15]
# 艾宾浩斯复习间隔映射（复习次序到天数的映射）
EBBINGHAUS_INTERVALS_MAP = {
    1: 2,  # 完成第1次复习后，第2次复习在 2 天后
    2: 4,  # 完成第2次复习后，第3次复习在 4 天后
    3: 7,  # 完成第3次复习后，第4次复习在 7 天后
    4: 15, # 完成第4次复习后，第5次复习在 15 天后
}


class LearningPlanListCreateView(generics.ListCreateAPIView):
    """
    列出和创建 LearningPlan（学习计划）。
    GET: 所有登录用户可以查看与自己相关的计划（老师看自己创建的，学生看分配给自己的）。
    POST: 仅限教师创建或更新计划。
    """
    serializer_class = LearningPlanSerializer
    # 基础权限控制
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """根据请求方法设置不同的权限"""
        if self.request.method == 'POST':
            # 创建操作需要教师权限
            return [permissions.IsAuthenticated(), IsRelatedTeacherOrAdmin()]
        # 查看列表只需要登录权限
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """根据用户角色获取学习计划列表"""
        user = self.request.user
        
        # 检查是否请求矩阵数据
        is_matrix_view = self.request.query_params.get('is_matrix_view') == 'true'
        matrix_select = None
        
        if is_matrix_view:
            # 只选择矩阵视图需要的字段
            matrix_select = ('id', 'student_id', 'vocabulary_book_id', 'words_per_day', 'start_date', 'is_active')
        
        # 检查用户是否为教师
        if hasattr(user, 'teacher_profile'):
            teacher = user.teacher_profile
            student_id = self.request.query_params.get('student_id', None)
            
            if student_id:
                try:
                    student_id_int = int(student_id)
                    # 直接返回该老师为特定学生创建的所有学习计划
                    queryset = LearningPlan.objects.filter(
                        teacher=teacher, 
                        student_id=student_id_int
                    )
                    
                    if matrix_select:
                        queryset = queryset.only(*matrix_select)
                    
                    return queryset.select_related('student__user', 'vocabulary_book').prefetch_related('units__reviews').order_by('-created_at') # 预取 units 和 reviews
                except (ValueError, TypeError):
                    return LearningPlan.objects.none() # 无效的 student_id 格式
            else:
                # 如果没有 student_id，则返回该教师创建的所有计划
                queryset = LearningPlan.objects.filter(teacher=teacher)
                
                if matrix_select:
                    queryset = queryset.only(*matrix_select)
                
                return queryset.select_related('student__user', 'vocabulary_book').prefetch_related('units__reviews').order_by('-created_at') # 预取并排序 # 预取 units 和 reviews

        # 检查用户是否为学生
        elif hasattr(user, 'student_profile'):
            student = user.student_profile
            queryset = LearningPlan.objects.filter(student=student)
            
            if matrix_select:
                queryset = queryset.only(*matrix_select)
            
            return queryset.select_related('teacher__user', 'vocabulary_book').prefetch_related('units__reviews').order_by('-created_at') # 预取 units 和 reviews

        # 用户既不是教师也不是与个人资料关联的学生
        return LearningPlan.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        
        # 检查是否请求矩阵数据
        is_matrix_view = request.query_params.get('is_matrix_view') == 'true'
        
        if page is not None:
            # 在这里传递上下文给序列化器
            context = {
                'include_detailed_units': True,
                'is_for_matrix': is_matrix_view
            }
            serializer = self.get_serializer(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        # 在这里传递上下文给序列化器
        context = {
            'include_detailed_units': True,
            'is_for_matrix': is_matrix_view
        }
        serializer = self.get_serializer(queryset, many=True, context=context)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """教师创建新学习计划或更新现有计划"""
        # 权限检查已由get_permissions处理，这里不再需要手动检查教师身份
        teacher = request.user.teacher_profile # 获取教师个人资料
        student_id = request.data.get('student_id')
        vocabulary_book_id = request.data.get('vocabulary_book_id')
        words_per_day_str = request.data.get('words_per_day', '20') # 获取为字符串
        is_active = request.data.get('is_active', True)

        # 验证 student_id
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response({"error": "无效的学生 ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 验证 vocabulary_book_id
        try:
            vocabulary_book = VocabularyBook.objects.get(pk=vocabulary_book_id)
        except VocabularyBook.DoesNotExist:
             return Response({"error": "无效的词汇书 ID"}, status=status.HTTP_400_BAD_REQUEST)

         # 验证 words_per_day
        try:
            words_per_day = int(words_per_day_str)
            if words_per_day < 5:
                 # （可选）提供默认值或引发特定错误
                return Response({"error": "每日单词数必须至少为 5"}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError):
            return Response({"error": "无效的每日单词数值，必须是数字。"}, status=status.HTTP_400_BAD_REQUEST)

        # 准备 update_or_create 的数据
        defaults = {
            'teacher': teacher,
            'words_per_day': words_per_day,
            'is_active': is_active
            # start_date 默认为模型的默认值，或可以在 request.data 中提供
        }
        if 'start_date' in request.data:
             defaults['start_date'] = request.data['start_date']

        regenerate_units = False
        try:
            with transaction.atomic():
                # 仅根据学生和词汇书查找现有计划
                existing_plan = LearningPlan.objects.filter(student=student, vocabulary_book=vocabulary_book).first()

                if existing_plan:
                     # 检查关键参数是否已更改，或者教师是否更改了所有权（如果允许）
                    if (existing_plan.words_per_day != words_per_day or
                        existing_plan.teacher != teacher): # 检查教师是否不同
                        regenerate_units = True
                     # 如果教师不同，则可能阻止更新或显式处理所有权转移
                else:
                    regenerate_units = True # 这是一个新计划

                # 如果将此计划设置为活动状态，则停用*同一学生*的其他*活动*计划
                if is_active:
                    student_active_plans = LearningPlan.objects.filter(student=student, is_active=True)
                    if existing_plan:
                        student_active_plans = student_active_plans.exclude(pk=existing_plan.pk)
                    student_active_plans.update(is_active=False)

                # 删除旧计划的学习单元
                if regenerate_units and existing_plan:
                    LearningUnit.objects.filter(learning_plan=existing_plan).delete()

                # 更新或创建计划
                learning_plan, created = LearningPlan.objects.update_or_create(
                    student=student,
                    vocabulary_book=vocabulary_book,
                    defaults=defaults
                )

                if regenerate_units:
                    total_words = vocabulary_book.word_count or 0
                    if total_words > 0:
                        # 创建第一个学习单元
                        first_unit = LearningUnit.objects.create(
                            learning_plan=learning_plan,
                            unit_number=1,
                            start_word_order=1,
                            end_word_order=min(words_per_day, total_words),
                            expected_learn_date=learning_plan.start_date if learning_plan.start_date else timezone.now().date()
                        )
                        print(f"Created first learning unit: {first_unit.unit_number} for plan {learning_plan.id}")

        except Exception as e:
             # 记录异常 e
             print(f"Error during plan creation/update: {e}")
             return Response({"error": "计划更新期间发生内部错误。"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(learning_plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
 
class MarkUnitAsLearnedView(APIView):
    """
    用于将指定的 LearningUnit 标记为已学习。
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentOwnerOrRelatedTeacherOrAdmin]
    
    def post(self, request, unit_id):
        # 仅通过 unit_id 获取 LearningUnit 对象
        unit = get_object_or_404(LearningUnit, pk=unit_id)
        
        # 从请求中获取 start_word_order 和 end_word_order（如果提供了的话）
        start_word_order = request.data.get('start_word_order')
        end_word_order = request.data.get('end_word_order')
        print(f"Received start_word_order: {start_word_order}, end_word_order: {end_word_order}")
        # 只有在单元从未被学习过的情况下才创建复习任务
        if not unit.is_learned:
            unit.is_learned = True
            unit.learned_at = timezone.now()
            
            # 如果前端传递了有效的 start_word_order 和 end_word_order，则更新它们
            if start_word_order is not None:
                try:
                    unit.start_word_order = int(start_word_order)
                except (ValueError, TypeError):
                    # 如果转换失败，保持原值不变
                    pass
                    
            if end_word_order is not None:
                try:
                    unit.end_word_order = int(end_word_order)
                except (ValueError, TypeError):
                    # 如果转换失败，保持原值不变
                    pass
            
            unit.save()
            
            # 创建第一个复习任务 (1天后)
            first_review_date = unit.learned_at.date() + timedelta(days=1)
            UnitReview.objects.create(
                learning_unit=unit,
                review_order=1,
                review_date=first_review_date
            )

            # --- 创建下一个学习单元（仅在首次学习完成时） ---
            learning_plan = unit.learning_plan # 获取关联的学习计划
            try:
                vocabulary_book = learning_plan.vocabulary_book
                total_words = vocabulary_book.word_count if vocabulary_book else 0
                words_per_day = learning_plan.words_per_day

                if total_words > 0 and words_per_day > 0:
                    total_units = math.ceil(total_words / words_per_day)
                    next_unit_number = unit.unit_number + 1

                    if next_unit_number <= total_units:
                        # 检查下一个单元是否已存在，避免重复创建
                        next_unit_exists = LearningUnit.objects.filter(
                            learning_plan=learning_plan,
                            unit_number=next_unit_number
                        ).exists()

                        if not next_unit_exists:
                            next_start_word_order = unit.end_word_order + 1
                            next_end_word_order = min(next_start_word_order + words_per_day - 1, total_words)

                            # 确定下一个单元的预期学习日期
                            # 核心逻辑：使用当前单元的预期日期加一天
                            if unit.expected_learn_date:
                                next_expected_learn_date = unit.expected_learn_date + timedelta(days=1)
                            else:
                                # Fallback: 如果当前单元没有预期日期，则基于当前完成时间计算
                                next_expected_learn_date = unit.learned_at.date() + timedelta(days=1)

                            LearningUnit.objects.create(
                                learning_plan=learning_plan,
                                unit_number=next_unit_number,
                                start_word_order=next_start_word_order,
                                end_word_order=next_end_word_order,
                                expected_learn_date=next_expected_learn_date
                            )
                            print(f"Created next learning unit: {next_unit_number} for plan {learning_plan.id}")

            except Exception as e:
                 # 记录创建下一个单元时可能发生的错误
                 print(f"Error creating next learning unit for plan {learning_plan.id} after unit {unit.id}: {e}")
        
        # 如果已经学习过，则更新此次学习单元和下一个待学习单元的单词范围
        else:
            unit.learned_at = timezone.now()
             
            if start_word_order is not None:
                try:
                    unit.start_word_order = int(start_word_order)
                except (ValueError, TypeError):
                    pass
                    
            if end_word_order is not None:
                try:
                    unit.end_word_order = int(end_word_order)
                except (ValueError, TypeError):
                    pass
             
            unit.save()
            
            # --- 非首次学习完成时，更新下一个学习单元 ---
            learning_plan = unit.learning_plan
            try:
                vocabulary_book = learning_plan.vocabulary_book
                total_words = vocabulary_book.word_count if vocabulary_book else 0
                words_per_day = learning_plan.words_per_day

                if total_words > 0 and words_per_day > 0:
                    total_units = math.ceil(total_words / words_per_day)
                    next_unit_number = unit.unit_number + 1

                    if next_unit_number <= total_units:
                        # 检查下一个单元是否存在
                        next_unit = LearningUnit.objects.filter(
                            learning_plan=learning_plan,
                            unit_number=next_unit_number
                        ).first()
                        
                        if next_unit:
                            # 更新下一个单元的单词范围
                            next_start_word_order = unit.end_word_order + 1
                            next_end_word_order = min(next_start_word_order + words_per_day, total_words)
                            
                            next_unit.start_word_order = next_start_word_order
                            next_unit.end_word_order = next_end_word_order
                            
                            next_unit.save()
                            print(f"Updated next learning unit: {next_unit_number} for plan {learning_plan.id}")
            except Exception as e:
                # 记录更新下一个单元时可能发生的错误
                print(f"Error updating next learning unit for plan {learning_plan.id} after unit {unit.id}: {e}")

        serializer = LearningUnitSerializer(unit)
        return Response(serializer.data)

class MarkReviewAsCompletedView(APIView):
    """
    标记当前轮次复习任务为已完成，并且更新UnitReview的数据。
    不会创建新的复习记录，而是更新当前记录的轮次和下次复习日期。
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentOwnerOrRelatedTeacherOrAdmin]
    
    # 使用全局定义的艾宾浩斯间隔
    review_intervals_days = EBBINGHAUS_INTERVALS_MAP
    
    def post(self, request, review_id):
        review = get_object_or_404(UnitReview, pk=review_id)
        
        # 只有在任务未完成时才进行处理
        if not review.is_completed:
            review.is_completed = True
            review.completed_at = timezone.now()
            
            # 检查是否需要更新到下一轮次
            current_order = review.review_order
            if current_order in self.review_intervals_days:
                days_interval = self.review_intervals_days[current_order]
                next_review_date = review.completed_at.date() + timedelta(days=days_interval)
                next_review_order = current_order + 1
                
                # 更新当前复习任务，而不是创建新的
                review.review_order = next_review_order
                review.review_date = next_review_date
                review.is_completed = False  # 重置为未完成状态，等待下次复习
                review.completed_at = None   # 清空完成时间
            
            review.save()
        
        # 如果 review 已经是 completed 状态，则直接返回当前状态
        serializer = UnitReviewSerializer(review)
        return Response(serializer.data)

class TodayLearningView(APIView):
    """
    获取指定学生的学习和复习单元。
    - 如果提供了 'day_number' 查询参数，则返回该天理论上的学习和复习单元 (基于艾宾浩斯计划)。
    - 如果未提供 'day_number'，则返回今天实际需要学习和复习的单元 (基于学习进度)。
    """
    permission_classes = [permissions.IsAuthenticated]
    EBINGHAUS_INTERVALS = [1, 2, 4, 7, 15] # 保持 Ebbinghaus 定义用于理论计算

    def _get_target_plan(self, user, request):
        """
        辅助方法：根据请求参数中的 'plan_id' 确定目标学习计划，并进行权限验证。
        所有用户类型都必须提供 'plan_id'。
        学生：验证计划是否属于自己。
        教师：验证计划是否由自己创建（除非是管理员）。
        管理员：可以访问任何计划。
        """
        # 统一要求 plan_id 参数
        plan_id_str = request.query_params.get('plan_id')
        if not plan_id_str:
            raise ValueError("必须提供 plan_id 参数。")

        try:
            plan_id = int(plan_id_str)
            # 尝试获取计划，预取关联数据以优化
            plan = LearningPlan.objects.select_related(
                'vocabulary_book', 'student', 'teacher' # 预取 teacher 以便验证
            ).get(pk=plan_id)

            # --- 权限验证 ---
            if hasattr(user, 'student_profile'):
                # 学生：检查计划是否属于自己
                if plan.student != user.student_profile:
                    raise PermissionDenied("您无权查看此学习计划。")
            elif hasattr(user, 'teacher_profile') and not user.is_staff:
                # 教师 (非管理员)：检查计划是否由自己创建
                if plan.teacher != user.teacher_profile:
                    raise PermissionDenied("您无权查看该学习计划的数据。")
            # 管理员 (user.is_staff) 可以访问任何计划，无需额外检查
            elif not user.is_staff: # 如果不是学生、不是教师、也不是管理员
                 raise PermissionDenied("无法识别的用户类型或权限不足。")


            return plan
        except LearningPlan.DoesNotExist:
            raise ValueError(f"未找到 ID 为 {plan_id_str} 的学习计划。")
        except (ValueError, TypeError): # 捕获 int() 可能的错误
             raise ValueError("无效的 plan_id 参数格式。")
        # PermissionDenied 会在这里被捕获并传递出去

    def _get_words_for_unit(self, unit: LearningUnit) -> list:
        """辅助方法：获取指定 LearningUnit 的单词列表"""
        if not unit or not unit.learning_plan.vocabulary_book or \
           unit.start_word_order is None or unit.end_word_order is None:
            return []

        words = BookWord.objects.filter(
            vocabulary_book=unit.learning_plan.vocabulary_book,
            word_order__gte=unit.start_word_order,
            word_order__lte=unit.end_word_order
        ).order_by('word_order')
        # 使用 BookWordSerializer 序列化单词
        return BookWordSerializer(words, many=True).data

    def _get_theoretical_tasks(self, request, target_plan, day_number, total_units, mode):
        """计算理论任务，并包含单词"""
        new_unit_data = None
        review_units_data = []
        response_data = {}

        if mode == 'new':
            if day_number <= total_units:
                new_unit = LearningUnit.objects.filter(
                    learning_plan=target_plan, unit_number=day_number
                ).first()
                if new_unit:
                    serializer = LearningUnitSerializer(new_unit, context={'request': request})
                    new_unit_data = serializer.data
                    new_unit_data['words'] = self._get_words_for_unit(new_unit) # 获取并添加单词

            response_data['new_unit'] = new_unit_data

        elif mode == 'review':
            review_unit_numbers = set()
            for interval in self.EBINGHAUS_INTERVALS:
                 original_learn_day = day_number - interval
                 if 1 <= original_learn_day <= total_units:
                    review_unit_numbers.add(original_learn_day)

            if review_unit_numbers:
                review_units_qs = LearningUnit.objects.filter(
                    learning_plan=target_plan, unit_number__in=list(review_unit_numbers)
                ).order_by('unit_number')
                for unit in review_units_qs:
                    serializer = LearningUnitSerializer(unit, context={'request': request})
                    unit_data = serializer.data
                    unit_data['words'] = self._get_words_for_unit(unit) # 获取并添加单词
                    review_units_data.append(unit_data)

            response_data['review_units'] = review_units_data

        response_data['day_number'] = day_number
        return response_data

    def _get_actual_tasks(self, request, target_plan, total_units, mode):
        """获取实际任务"""
        new_unit_data = None
        review_units_data = []
        response_data = {}

        if mode == 'new':
            # --- 计算下一个新学单元 ---
            latest_learned_unit = LearningUnit.objects.filter(
                learning_plan=target_plan,
                is_learned=True
            ).order_by('-unit_number').first()

            current_day_number = 1
            today = timezone.now().date()
            should_return_today_learned = False
            
            if latest_learned_unit:
                current_day_number = latest_learned_unit.unit_number + 1
                # 检查最近学习单元是否是今天完成的
                if latest_learned_unit.learned_at and latest_learned_unit.learned_at.date() == today:
                    should_return_today_learned = True
                    current_day_number = latest_learned_unit.unit_number

            new_unit_to_learn = None
            if current_day_number <= total_units:
                new_unit_to_learn = LearningUnit.objects.filter(
                    learning_plan=target_plan,
                    unit_number=current_day_number
                ).select_related(
                    'learning_plan__student__user',
                    'learning_plan__vocabulary_book'
                ).first()
            
            if new_unit_to_learn:
                serializer = LearningUnitSerializer(new_unit_to_learn, context={'request': request})
                new_unit_data = serializer.data
                new_unit_data['words'] = self._get_words_for_unit(new_unit_to_learn) # 获取并添加单词

            response_data['new_unit'] = new_unit_data
        
        elif mode == 'review':
            # 获取学生当前已学习的最大单元编号
            latest_learned_unit = LearningUnit.objects.filter(
                learning_plan=target_plan,
                is_learned=True
            ).order_by('-unit_number').first()
            
            max_unit_number = 0
            if latest_learned_unit:
                max_unit_number = latest_learned_unit.unit_number
            
            # 查询所有未完成的复习任务
            # 只获取单元编号不超过当前最新学习单元的复习任务
            pending_reviews = UnitReview.objects.filter(
                learning_unit__learning_plan=target_plan,
                is_completed=False,
                learning_unit__unit_number__lte=max_unit_number  # 确保不超过当前最新学习单元
            ).select_related('learning_unit').order_by('learning_unit__unit_number')

            # 获取这些复习任务关联的不重复的学习单元
            units_to_review = {review.learning_unit for review in pending_reviews}

            for unit in units_to_review:
                serializer = LearningUnitSerializer(unit, context={'request': request})
                unit_data = serializer.data
                unit_data['words'] = self._get_words_for_unit(unit) # 获取并添加单词
                review_units_data.append(unit_data)

            response_data['review_units'] = review_units_data

        return response_data

    def get(self, request):
        target_plan = None # 初始化目标计划
        try:
            # 尝试获取目标学习计划 (现在所有用户都需要 plan_id)
            target_plan = self._get_target_plan(request.user, request)
        except (ValueError, PermissionDenied) as e:
            # 处理获取计划过程中的错误 (权限不足、参数错误、未找到计划等)
            status_code = status.HTTP_403_FORBIDDEN if isinstance(e, PermissionDenied) else status.HTTP_400_BAD_REQUEST
            return Response({"error": str(e)}, status=status_code)

        # --- 读取 mode 参数 ---
        mode = request.query_params.get('mode')
        if mode not in ['new', 'review']:
            return Response({"error": "必须提供有效的 mode 参数 ('new' 或 'review')。"}, status=status.HTTP_400_BAD_REQUEST)

        # 如果上面的 try 块成功，target_plan 肯定是一个有效的、用户有权访问的计划
        # 不再需要检查 target_plan is None 的情况，因为如果计划不存在或无权访问，会抛出异常

        # --- 从这里开始，我们肯定有一个有效的 target_plan ---
        total_words = target_plan.vocabulary_book.word_count if target_plan.vocabulary_book else 0
        words_per_day = target_plan.words_per_day

        if not total_words or not words_per_day or words_per_day <= 0:
             return Response({"error": "学习计划的词汇书或每日单词数无效。"}, status=status.HTTP_400_BAD_REQUEST)

        total_units = math.ceil(total_words / words_per_day)

        day_number_str = request.query_params.get('day_number')

        response_data = {}
        if day_number_str:
            try:
                day_number = int(day_number_str)
                if day_number < 1:
                    raise ValueError("day_number 必须是正整数。")
                # 调用理论任务计算，传入 target_plan 和 mode
                response_data = self._get_theoretical_tasks(request, target_plan, day_number, total_units, mode)

            except (ValueError, TypeError):
                return Response({"error": "无效的 day_number 参数。"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # 调用实际任务计算，传入 target_plan 和 mode
            response_data = self._get_actual_tasks(request, target_plan, total_units, mode)

        return Response(response_data)


class AddNewWordsView(APIView):
    """
    获取额外的新单词学习。
    需要 plan_id, unit_id, count 参数。
    """
    permission_classes = [permissions.IsAuthenticated, IsStudentOwnerOrRelatedTeacherOrAdmin]
    
    def get(self, request, plan_id):
        try:
            # 获取参数
            unit_id = request.query_params.get('unit_id')
            count_str = request.query_params.get('count', '5')
            
            # 验证参数
            if not unit_id:
                return Response({"error": "必须提供unit_id参数"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                count = int(count_str)
                if count <= 0:
                    return Response({"error": "count必须为正整数"}, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({"error": "无效的count参数格式"}, status=status.HTTP_400_BAD_REQUEST)
            
            # 获取学习计划和单元
            plan = get_object_or_404(LearningPlan, pk=plan_id)
            unit = get_object_or_404(LearningUnit, pk=unit_id, learning_plan=plan)
            
            # 获取词汇书
            vocabulary_book = plan.vocabulary_book
            if not vocabulary_book:
                return Response({"error": "该学习计划没有关联的词汇书"}, status=status.HTTP_400_BAD_REQUEST)
            
            # 确定单词范围
            total_words = vocabulary_book.word_count
            current_end = unit.end_word_order or 0
            new_end = min(current_end + count, total_words)
            
            if current_end >= total_words:
                return Response({"error": "已达到词汇书最大单词数量"}, status=status.HTTP_400_BAD_REQUEST)
            
            # 获取额外的单词
            additional_words = BookWord.objects.filter(
                vocabulary_book=vocabulary_book,
                word_order__gt=current_end,
                word_order__lte=new_end
            ).order_by('word_order')
            
            # 序列化单词数据
            serializer = BookWordSerializer(additional_words, many=True)
            
            return Response({
                "plan_id": plan_id,
                "unit_id": unit_id,
                "original_end_word_order": current_end,
                "new_end_word_order": new_end,
                "words": serializer.data
            })
            
        except Exception as e:
            return Response({"error": f"获取额外单词时发生错误: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EbinghausMatrixDataView(APIView):
    """
    专门用于艾宾浩斯矩阵的轻量级数据API。
    只返回矩阵显示所需的必要数据。
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            # 获取学习计划ID
            plan_id_str = request.query_params.get('plan_id')
            if not plan_id_str:
                return Response({"error": "必须提供plan_id参数"}, status=status.HTTP_400_BAD_REQUEST)
            
            plan_id = int(plan_id_str)
            
            # 验证用户是否有权访问此计划
            user = request.user
            plan = LearningPlan.objects.get(pk=plan_id)
            
            # 权限验证
            if hasattr(user, 'student_profile'):
                if plan.student != user.student_profile:
                    return Response({"error": "无权访问此计划"}, status=status.HTTP_403_FORBIDDEN)
            elif hasattr(user, 'teacher_profile') and not user.is_staff:
                if plan.teacher != user.teacher_profile:
                    return Response({"error": "无权访问此计划"}, status=status.HTTP_403_FORBIDDEN)
            elif not user.is_staff:
                return Response({"error": "无效用户类型"}, status=status.HTTP_403_FORBIDDEN)
            
            # 只查询需要的数据
            learning_plan = LearningPlan.objects.select_related('vocabulary_book').prefetch_related(
                # 只预加载必要的字段
                'units__reviews'
            ).get(pk=plan_id)
            
            # 使用带上下文的序列化器
            serializer = LearningPlanSerializer(
                learning_plan, 
                context={'is_for_matrix': True}
            )
            
            # 提取只需要的数据
            response_data = {
                'id': serializer.data['id'],
                'total_days': serializer.data['total_days'],
                'words_per_day': serializer.data['words_per_day'],
                'total_words': learning_plan.vocabulary_book.word_count if learning_plan.vocabulary_book else 0,
                'units': serializer.data['units']
            }
            
            return Response(response_data)
        
        except LearningPlan.DoesNotExist:
            return Response({"error": f"未找到ID为{plan_id_str}的学习计划"}, status=status.HTTP_404_NOT_FOUND)
        except (ValueError, TypeError):
            return Response({"error": "无效的plan_id格式"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"获取矩阵数据时出错: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)