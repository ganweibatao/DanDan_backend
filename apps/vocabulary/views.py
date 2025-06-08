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
    queryset = VocabularyBook.objects.all()
    serializer_class = VocabularyBookSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'word_count', 'created_at']
    
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
    




# 词库分页
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

# 词库书籍列表API
class VocabularyBookListView(generics.ListAPIView):
    queryset = VocabularyBook.objects.all().order_by('name')
    serializer_class = VocabularyBookSerializer
    permission_classes = [permissions.IsAuthenticated]

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
        return BookWord.objects.filter(vocabulary_book_id=book_id).order_by('word_order').select_related('word_basic')

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
    - GET /api/vocabulary/known-words/?student=<student_id> (List known words for a student)
    - DELETE /api/vocabulary/known-words/unmark/ (Unmark word)
      Body: { "student": <student_id>, "word": <word_basic_id> }
    """
    queryset = StudentKnownWord.objects.all()
    serializer_class = StudentKnownWordSerializer
    permission_classes = [permissions.IsAuthenticated] # Protect this endpoint

    def get_queryset(self):
        queryset = super().get_queryset()
        student_id = self.request.query_params.get('student')
        if student_id:
            # Ensure student_id is an integer before filtering
            try:
                student_id = int(student_id)
                queryset = queryset.filter(student_id=student_id)
            except ValueError:
                # Handle invalid student_id (e.g., return empty or raise error)
                return StudentKnownWord.objects.none()
        
        # 新增：按 book_id 筛选
        book_id = self.request.query_params.get('book')
        if book_id:
            try:
                book_id = int(book_id)
                # 获取该书中的所有 word_basic_id
                word_ids_in_book = BookWord.objects.filter(
                    vocabulary_book_id=book_id
                ).values_list('word_basic_id', flat=True)
                # 筛选出在本书中的已知单词
                queryset = queryset.filter(word_id__in=word_ids_in_book)
            except (ValueError, TypeError):
                return StudentKnownWord.objects.none()

        return queryset

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