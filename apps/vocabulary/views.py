from rest_framework import viewsets, permissions, filters, status, serializers, generics, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.http import HttpResponse, JsonResponse
from .models import VocabularyBook, BookWord, WordBasic, StudentKnownWord
from .serializers import (
    VocabularyBookSerializer, BookWordSerializer,
    WordBasicSerializer, StudentKnownWordSerializer,
    BookWordUpdateSerializer
)
import csv
import io
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from apps.accounts.models import Student
import requests
import re

# 尝试导入Student模型
try:
    from apps.accounts.models import Student
except ImportError:
    try:
        from accounts.models import Student
    except ImportError:
        # 如果无法导入Student，定义一个空的get_student函数
        def get_student(user):
            return None
else:
    # 如果成功导入Student，定义正常的get_student函数
    def get_student(user):
        try:
            return user.student
        except:
            return None

def get_student_or_none(user):
    from apps.accounts.models import Student
    try:
        return Student.objects.get(user=user)
    except Student.DoesNotExist:
        return None

# 新增视图集
class VocabularyBookViewSet(viewsets.ModelViewSet):
    """
    API端点，允许词汇书籍查看或编辑
    """
    serializer_class = VocabularyBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'word_count', 'created_at']
    
    def get_queryset(self):
        """获取当前用户的自定义词库和系统预设词库"""
        user = self.request.user
        return VocabularyBook.objects.filter(
            models.Q(is_system_preset=True) |  # 系统预设词库
            models.Q(created_by=user)          # 用户自己创建的词库
        ).order_by('name')
    
    def perform_create(self, serializer):
        """创建词库时自动设置创建者"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def system_presets(self, request):
        """获取系统预设的词汇书籍"""
        books = VocabularyBook.objects.filter(is_system_preset=True)
        serializer = self.get_serializer(books, many=True)
        return Response(serializer.data)

class BookWordViewSet(viewsets.ModelViewSet):
    """
    API端点，允许词汇书中的单词查看或编辑
    """
    queryset = BookWord.objects.all()
    serializer_class = BookWordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vocabulary_book']
    search_fields = ['word_basic__word', 'example_sentence']
    ordering_fields = ['word_order', 'word_basic__word', 'created_at']
    
    def get_serializer_class(self):
        """根据请求动态选择序列化器"""
        if self.action in ['update', 'partial_update']:
            return BookWordUpdateSerializer
        return BookWordSerializer
    
    @action(detail=False, methods=['get'])
    def by_book(self, request):
        """按词汇书获取单词"""
        book_id = request.query_params.get('book_id')
        if not book_id:
            return Response({"error": "请提供book_id参数"}, status=400)
            
        try:
            words = BookWord.objects.filter(vocabulary_book_id=book_id)
            page = self.paginate_queryset(words)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
                
            serializer = self.get_serializer(words, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": f"获取单词失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='batch')
    def get_words_by_texts(self, request):
        """
        通过单词文本批量查询词书中对应的单词详情
        POST /api/vocabulary/book-words/batch/
        Body: {
            "book_id": 1,
            "word_texts": ["encourage", "retire", "cheerful", ...]
        }
        """
        book_id = request.data.get('book_id')
        word_texts = request.data.get('word_texts', [])
        
        if not book_id:
            return Response({"error": "请提供book_id参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not word_texts or not isinstance(word_texts, list):
            return Response({"error": "请提供word_texts数组参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        if len(word_texts) > 100:  # 限制批量查询数量
            return Response({"error": "单次查询单词数量不能超过100个"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 验证词书是否存在
            vocabulary_book = get_object_or_404(VocabularyBook, id=book_id)
            
            # 通过单词文本查询对应的单词详情
            words = BookWord.objects.filter(
                vocabulary_book_id=book_id,
                word_basic__word__in=word_texts,
                word_basic__isnull=False
            ).select_related('word_basic', 'vocabulary_book').order_by('word_order')
            
            # 序列化返回数据
            serializer = self.get_serializer(words, many=True)
            
            return Response({
                "words": serializer.data,
                "total_requested": len(word_texts),
                "total_found": words.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
                         return Response({
                 "error": f"批量查询单词失败: {str(e)}"
             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BookWordBatchQueryView(APIView):
    """
    批量查询词书中单词详情的独立视图
    POST /api/vocabulary/books/{book_id}/words/batch/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, book_id):
        """
        通过单词文本批量查询词书中对应的单词详情
        Body: {
            "word_texts": ["encourage", "retire", "cheerful", ...]
        }
        """
        word_texts = request.data.get('word_texts', [])
        
        if not word_texts or not isinstance(word_texts, list):
            return Response({"error": "请提供word_texts数组参数"}, status=status.HTTP_400_BAD_REQUEST)
        
        if len(word_texts) > 1000:  # 限制批量查询数量
            return Response({"error": "单次查询单词数量不能超过100个"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 验证词书是否存在
            vocabulary_book = get_object_or_404(VocabularyBook, id=book_id)
            
            # 通过单词文本查询对应的单词详情
            words = BookWord.objects.filter(
                vocabulary_book_id=book_id,
                word_basic__word__in=word_texts,
                word_basic__isnull=False
            ).select_related('word_basic', 'vocabulary_book').order_by('word_order')
            
            # 序列化返回数据
            serializer = BookWordSerializer(words, many=True)
            
            return Response({
                "words": serializer.data,
                "total_requested": len(word_texts),
                "total_found": words.count()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"批量查询单词失败: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




# 词库分页
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

# 词库书籍列表API
class VocabularyBookListView(generics.ListAPIView):
    serializer_class = VocabularyBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """获取当前用户的自定义词库和系统预设词库"""
        user = self.request.user
        return VocabularyBook.objects.filter(
            models.Q(is_system_preset=True) |  # 系统预设词库
            models.Q(created_by=user)          # 用户自己创建的词库
        ).order_by('name')

# 词库书籍详情API
class VocabularyBookDetailView(generics.RetrieveAPIView):
    queryset = VocabularyBook.objects.all()
    serializer_class = VocabularyBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

# 词库单词列表API
class BookWordListView(generics.ListAPIView):
    serializer_class = BookWordSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        book_id = self.kwargs['book_id']
        # 确保包含word_basic关联，并过滤掉没有word_basic的记录
        return BookWord.objects.filter(
            vocabulary_book_id=book_id,
            word_basic__isnull=False  # 确保word_basic存在
        ).order_by('word_order').select_related('word_basic')

# 词库单词详情API
class BookWordDetailView(generics.RetrieveAPIView):
    serializer_class = BookWordSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return BookWord.objects.all().select_related('word_basic')



# 获取单词基本信息API
class WordBasicListView(generics.ListAPIView):
    queryset = WordBasic.objects.all()
    serializer_class = WordBasicSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

# 搜索单词API
class WordSearchView(generics.ListAPIView):
    serializer_class = WordBasicSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if query:
            return WordBasic.objects.filter(word__icontains=query)
        return WordBasic.objects.none()

# 导入单词视图
class ImportWordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, book_id):
        """批量导入单词API"""
        csv_file = request.FILES.get('csv_file')
        
        if not csv_file:
            return Response({"error": "请提供CSV文件"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            book = VocabularyBook.objects.get(id=book_id)
            
            # 尝试多种编码方式读取文件
            file_content = csv_file.read()
            decoded_file = None
            
            # 尝试的编码列表
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig', 'latin1']
            
            for encoding in encodings:
                try:
                    decoded_file = file_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if decoded_file is None:
                return Response(
                    {"error": "无法解析文件编码，请确保文件是UTF-8、GBK或GB2312编码"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 预处理CSV内容，处理可能的格式问题
            lines = decoded_file.splitlines()
            if not lines:
                return Response(
                    {"error": "文件为空"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # 使用更强健的CSV解析
            try:
                io_string = io.StringIO(decoded_file)
                # 设置更宽松的CSV解析选项
                reader = csv.DictReader(
                    io_string, 
                    delimiter=',', 
                    quotechar='"', 
                    skipinitialspace=True,
                    quoting=csv.QUOTE_MINIMAL
                )
                
                # 验证表头
                fieldnames = reader.fieldnames
                if not fieldnames or 'word' not in fieldnames or 'chinese_meaning' not in fieldnames:
                    return Response(
                        {"error": "CSV文件格式错误。必须包含'word'和'chinese_meaning'列"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except Exception as csv_error:
                return Response(
                    {"error": f"CSV文件格式错误: {str(csv_error)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            word_count = 0
            imported_words = []
            
            # 获取当前词汇书中最大的word_order
            max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                models.Max('word_order')
            ).get('word_order__max') or 0
            
            for row in reader:
                # 跳过空行或无效数据
                if not row.get('word') or not row.get('word').strip():
                    continue
                if not row.get('chinese_meaning') or not row.get('chinese_meaning').strip():
                    continue
                
                # 创建或更新单词
                max_order += 1
                
                # 处理词性字段
                part_of_speech = row.get('part_of_speech', '')
                chinese_meaning = row['chinese_meaning']
                
                # 构建meanings JSON结构
                meanings = []
                if part_of_speech and chinese_meaning:
                    meanings.append({
                        'pos': part_of_speech,
                        'meaning': chinese_meaning
                    })
                elif chinese_meaning:
                    meanings.append({
                        'pos': '',
                        'meaning': chinese_meaning
                    })
                
                # 创建或更新WordBasic
                word_basic, _ = WordBasic.objects.get_or_create(
                    word=row['word'],
                    defaults={
                        'phonetic_symbol': row.get('phonetic_symbol', ''),
                        'uk_pronunciation': row.get('uk_pronunciation', ''),
                        'us_pronunciation': row.get('us_pronunciation', '')
                    }
                )
                
                word, created = BookWord.objects.update_or_create(
                    vocabulary_book=book,
                    word_basic=word_basic,
                    defaults={
                        'word_order': int(row.get('word_order')) if row.get('word_order') and row.get('word_order').strip() else max_order,
                        'meanings': meanings,
                        'example_sentence': row.get('example_sentence', ''),
                    }
                )
                word_count += 1
                imported_words.append(BookWordSerializer(word).data)
            
            # 更新词汇书的词汇量
            total_words = BookWord.objects.filter(vocabulary_book=book).count()
            book.word_count = total_words
            book.save()
            
            return Response({
                "message": f"成功导入 {word_count} 个单词到词汇书 '{book.name}'",
                "imported_words": imported_words
            }, status=status.HTTP_201_CREATED)
        
        except VocabularyBook.DoesNotExist:
            return Response({"error": "指定的词汇书不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"导入失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# 导出单词视图
class ExportWordsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, book_id):
        """导出词汇书中的单词为CSV文件"""
        try:
            book = VocabularyBook.objects.get(id=book_id)
            words = BookWord.objects.filter(vocabulary_book=book).order_by('word_order')
            
            if not words:
                return Response({"error": "词汇书中没有单词"}, status=status.HTTP_404_NOT_FOUND)
            
            # 创建CSV响应
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{book.name}_words.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['word', 'phonetic_symbol', 'part_of_speech', 'chinese_meaning', 'example_sentence', 'word_order'])
            
            for word in words:
                # 从meanings JSON中提取词性和释义
                part_of_speech = ''
                chinese_meaning = ''
                if word.meanings and len(word.meanings) > 0:
                    first_meaning = word.meanings[0]
                    part_of_speech = first_meaning.get('pos', '')
                    chinese_meaning = first_meaning.get('meaning', '')
                
                writer.writerow([
                    word.word_basic.word if word.word_basic else '',
                    word.word_basic.phonetic_symbol if word.word_basic else '',
                    part_of_speech,
                    chinese_meaning,
                    word.example_sentence or '',
                    word.word_order
                ])
            
            return response
        
        except VocabularyBook.DoesNotExist:
            return Response({"error": "指定的词汇书不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"导出失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def iciba_suggest(request):
    """
    前端传递word参数，后端请求iciba.com suggest接口，返回原始json
    """
    word = request.GET.get('word', '').strip()
    if not word:
        return Response({'error': '缺少word参数'}, status=400)
    try:
        url = 'https://dict-mobile.iciba.com/interface/index.php'
        params = {
            'c': 'word',
            'm': 'getsuggest',
            'nums': 5,
            'is_need_mean': 1,
            'word': word
        }
        resp = requests.get(url, params=params, timeout=5)
        resp.raise_for_status()
        return Response(resp.json())
    except Exception as e:
        return Response({'error': f'iciba suggest请求失败: {str(e)}'}, status=500)

class StudentKnownWordViewSet(viewsets.ModelViewSet):
    """
    API endpoint for students to manage their known words.
    - POST /api/vocabulary/known-words/ (Mark word as known)
      Body: { "student": <student_id>, "word": <word_basic_id> }
    - GET /api/vocabulary/known-words/?student=<student_id> (List all known words for a student)
    - GET /api/vocabulary/known-words/?student=<student_id>&book=<book_id> (List all known words with details for a student in a book)
    - DELETE /api/vocabulary/known-words/unmark/ (Unmark word)
      Body: { "student": <student_id>, "word": <word_basic_id> }
    """
    queryset = StudentKnownWord.objects.all()
    serializer_class = StudentKnownWordSerializer
    permission_classes = [permissions.IsAuthenticated] # Protect this endpoint
    pagination_class = None  # 禁用分页，一次性返回所有数据

    def get_serializer_class(self):
        """根据是否有book参数选择不同的序列化器"""
        book_id = self.request.query_params.get('book')
        if book_id and self.action == 'list':
            from .serializers import StudentKnownWordDetailSerializer
            return StudentKnownWordDetailSerializer
        return self.serializer_class

    def get_serializer_context(self):
        """传递book_id到序列化器context"""
        context = super().get_serializer_context()
        book_id = self.request.query_params.get('book')
        if book_id:
            try:
                context['book_id'] = int(book_id)
            except (ValueError, TypeError):
                pass
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student')
        
        if not student_id:
            return StudentKnownWord.objects.none()
            
        # 确保student_id是有效整数
        try:
            student_id = int(student_id)
        except ValueError:
            return StudentKnownWord.objects.none()
        
        # 基础查询：按学生筛选
        queryset = queryset.filter(student_id=student_id)
        
        # 按词书筛选（如果提供了book参数）
        book_id = self.request.query_params.get('book')
        if book_id:
            try:
                book_id = int(book_id)
                # 性能优化：使用exists子查询而不是values_list + __in
                queryset = queryset.filter(
                    word_id__in=BookWord.objects.filter(
                        vocabulary_book_id=book_id
                    ).values_list('word_basic_id', flat=True)
                )
            except (ValueError, TypeError):
                return StudentKnownWord.objects.none()

        # 性能优化：预加载相关数据
        return queryset.select_related('student', 'word').order_by('-marked_at')

    def list(self, request, *args, **kwargs):
        """重写list方法，添加性能监控和数据量检查"""
        import time
        start_time = time.time()
        
        queryset = self.filter_queryset(self.get_queryset())
        
        # 数据量检查，防止返回过多数据
        count = queryset.count()
        if count > 10000:  # 如果超过1万条记录，建议使用分页
            return Response({
                "error": "数据量过大，请联系管理员优化查询条件",
                "count": count
            }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        
        serializer = self.get_serializer(queryset, many=True)
        
        end_time = time.time()
        response_data = {
            "count": count,
            "results": serializer.data
        }
        
        # 添加性能信息到响应头
        response = Response(response_data)
        response['X-Query-Time'] = f"{(end_time - start_time):.3f}s"
        response['X-Result-Count'] = str(count)
        
        return response

    # Create is handled by ModelViewSet by default if student and word are PKs
    # POST to /api/vocabulary/known-words/
    # Body: { "student": <student_id>, "word": <word_id> }

    @action(detail=False, methods=['delete'], url_path='unmark')
    def unmark_word(self, request):
        student_id = request.data.get('student')
        word_id = request.data.get('word')

        if not student_id or not word_id:
            return Response({"error": "Student ID and Word ID are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            student_id = int(student_id)
            word_id = int(word_id)
        except ValueError:
            return Response({"error": "Invalid Student ID or Word ID."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            known_word = StudentKnownWord.objects.get(student_id=student_id, word_id=word_id)
            known_word.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except StudentKnownWord.DoesNotExist:
            return Response({"error": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # --- NEW: 批量标记已掌握单词 ---
    @action(detail=False, methods=['post'], url_path='mark-batch')
    def mark_batch(self, request):
        """批量将单词标记为已掌握，不影响原有单条 POST 接口。\n
        请求体示例：{ "student": 10, "word_ids": [1,2,3] } 或 { "student": 10, "words": [1,2,3] }"""

        student_id = request.data.get('student')
        word_ids = request.data.get('word_ids') or request.data.get('words')

        # 基本校验
        if not student_id or not isinstance(word_ids, (list, tuple)) or not word_ids:
            return Response(
                {"error": "需要提供 student 以及非空的 word_ids 列表"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            return Response({"error": "student 参数必须是整数"}, status=status.HTTP_400_BAD_REQUEST)

        # 过滤掉无法转换的 word_id
        valid_word_ids = []
        for wid in word_ids:
            try:
                valid_word_ids.append(int(wid))
            except (ValueError, TypeError):
                pass

        if not valid_word_ids:
            return Response({"error": "word_ids 列表中没有有效的整数ID"}, status=status.HTTP_400_BAD_REQUEST)

        # 去重
        valid_word_ids = list(set(valid_word_ids))

        # 查询已存在的记录，避免重复创建
        existing_ids = set(
            StudentKnownWord.objects.filter(student_id=student_id, word_id__in=valid_word_ids)
            .values_list('word_id', flat=True)
        )

        to_create_ids = [wid for wid in valid_word_ids if wid not in existing_ids]

        created_objects = [
            StudentKnownWord(student_id=student_id, word_id=wid) for wid in to_create_ids
        ]

        # 批量创建
        StudentKnownWord.objects.bulk_create(created_objects, ignore_conflicts=True)

        return Response({
            "success": True,
            "student": student_id,
            "created_count": len(created_objects),
            "skipped_existing": list(existing_ids),
        }, status=status.HTTP_201_CREATED)

class ProxyYoudaoPronunciationView(APIView):
    """代理有道词典发音请求，解决跨域问题"""
    
    def get(self, request):
        word = request.GET.get('word', '')
        if not word:
            return JsonResponse({'error': 'Word parameter is required'}, status=400)
        
        # 将所有非字母和非空格的字符替换为空格
        word = re.sub(r'[^a-zA-Z\s]', ' ', word)
        # 去掉多余的空格（例如多个空格变成一个空格）
        word = re.sub(r'\s+', ' ', word).strip()
        
        if not word:
            return JsonResponse({'error': 'Word parameter is invalid after formatting'}, status=400)
        
        try:
            youdao_url = f'https://dict.youdao.com/dictvoice?audio={word}'
            response = requests.get(youdao_url, timeout=10)
            
            if response.status_code == 200:
                return HttpResponse(
                    response.content,
                    content_type=response.headers.get('Content-Type', 'audio/mpeg')
                )
            else:
                return JsonResponse(
                    {'error': f'Failed to fetch pronunciation: {response.status_code}'},
                    status=response.status_code
                )
        except requests.exceptions.Timeout:
            return JsonResponse({'error': 'Request timeout'}, status=504)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500) 