from rest_framework import viewsets, permissions, filters, status, serializers, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.http import HttpResponse
from .models import VocabularyBook, BookWord, StudentCustomization, WordBasic
from .serializers import (
    VocabularyBookSerializer, BookWordSerializer, StudentCustomizationSerializer,
    BookWordWithCustomizationSerializer, WordBasicSerializer
)
import csv
import io
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from apps.accounts.models import Student

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
    filterset_fields = ['vocabulary_book', 'difficulty_level']
    search_fields = ['word', 'chinese_meaning', 'example_sentence']
    ordering_fields = ['word_order', 'word', 'difficulty_level', 'created_at']
    
    def get_serializer_class(self):
        """根据请求动态选择序列化器"""
        if self.request.query_params.get('with_customization') == 'true':
            return BookWordWithCustomizationSerializer
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
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def import_words(self, request):
        """批量导入单词API"""
        csv_file = request.FILES.get('csv_file')
        book_id = request.data.get('book_id')
        
        if not csv_file or not book_id:
            return Response({"error": "请提供CSV文件和词汇书ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            book = VocabularyBook.objects.get(id=book_id)
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            word_count = 0
            imported_words = []
            
            # 获取当前词汇书中最大的word_order
            max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                models.Max('word_order')
            ).get('word_order__max') or 0
            
            for row in reader:
                # 确保CSV文件包含所需字段
                if 'word' not in row or 'chinese_meaning' not in row:
                    return Response(
                        {"error": "CSV文件格式错误。必须包含'word'和'chinese_meaning'列"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 创建或更新单词
                max_order += 1
                
                # 处理词性字段
                part_of_speech = row.get('part_of_speech', '')
                # 不再验证词性是否在预定义选项中，直接使用用户输入的值
                
                word, created = BookWord.objects.update_or_create(
                    vocabulary_book=book,
                    word=row['word'],
                    defaults={
                        'word_order': int(row.get('word_order')) if row.get('word_order') and row.get('word_order').strip() else max_order,
                        'phonetic_symbol': row.get('phonetic_symbol', ''),
                        'part_of_speech': part_of_speech,
                        'chinese_meaning': row['chinese_meaning'],
                        'example_sentence': row.get('example_sentence', ''),
                        'difficulty_level': int(row.get('difficulty_level', 1))
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

class StudentCustomizationViewSet(viewsets.ModelViewSet):
    """
    API端点，允许学生自定义单词查看或编辑
    """
    serializer_class = StudentCustomizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """只返回当前学生的自定义内容"""
        try:
            student = get_student(self.request.user)
            if not student:
                return StudentCustomization.objects.none()
            return StudentCustomization.objects.filter(student=student)
        except:
            return StudentCustomization.objects.none()
    
    def perform_create(self, serializer):
        """创建时自动关联当前学生"""
        student = get_student(self.request.user)
        if not student:
            raise serializers.ValidationError("用户必须是学生才能自定义单词")
        serializer.save(student=student)
    
    @action(detail=False, methods=['post'])
    def customize_word(self, request):
        """创建或更新学生对单词的自定义内容"""
        student = get_student(request.user)
        if not student:
            return Response({"error": "用户必须是学生才能自定义单词"}, status=403)
            
        word_id = request.data.get('word_id')
        chinese_meaning = request.data.get('chinese_meaning')
        example_sentence = request.data.get('example_sentence')
        
        if not word_id:
            return Response({"error": "请提供word_id参数"}, status=400)
            
        try:
            word = BookWord.objects.get(id=word_id)
        except BookWord.DoesNotExist:
            return Response({"error": "指定的单词不存在"}, status=404)
            
        # 创建或更新自定义内容
        customization, created = StudentCustomization.objects.update_or_create(
            student=student,
            word=word,
            defaults={
                'chinese_meaning': chinese_meaning,
                'example_sentence': example_sentence
            }
        )
        
        serializer = StudentCustomizationSerializer(customization)
        return Response(serializer.data)

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

# 学生单词自定义列表API
class StudentCustomizationListView(generics.ListCreateAPIView):
    serializer_class = StudentCustomizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return StudentCustomization.objects.filter(student=student).select_related('word_basic')

    def perform_create(self, serializer):
        student = get_object_or_404(Student, user=self.request.user)
        serializer.save(student=student)

# 学生单词自定义详情API
class StudentCustomizationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StudentCustomizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        student = get_object_or_404(Student, user=self.request.user)
        return StudentCustomization.objects.filter(student=student)

# 获取用户自定义或默认单词API
class UserWordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, word_basic_id):
        student = get_object_or_404(Student, user=request.user)
        word_basic = get_object_or_404(WordBasic, id=word_basic_id)
        
        # 尝试获取学生自定义内容
        custom_word = StudentCustomization.objects.filter(
            student=student,
            word_basic=word_basic
        ).first()
        
        if custom_word:
            serializer = StudentCustomizationSerializer(custom_word)
            return Response(serializer.data)
        
        # 如果没有自定义，返回默认数据
        book_word = BookWord.objects.filter(word_basic=word_basic).first()
        if book_word:
            serializer = BookWordSerializer(book_word)
            return Response(serializer.data)
        
        # 如果没有任何相关数据，返回404
        return Response({"detail": "Word not found"}, status=status.HTTP_404_NOT_FOUND)

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
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            word_count = 0
            imported_words = []
            
            # 获取当前词汇书中最大的word_order
            max_order = BookWord.objects.filter(vocabulary_book=book).aggregate(
                models.Max('word_order')
            ).get('word_order__max') or 0
            
            for row in reader:
                # 确保CSV文件包含所需字段
                if 'word' not in row or 'chinese_meaning' not in row:
                    return Response(
                        {"error": "CSV文件格式错误。必须包含'word'和'chinese_meaning'列"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # 创建或更新单词
                max_order += 1
                
                # 处理词性字段
                part_of_speech = row.get('part_of_speech', '')
                
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
                        'part_of_speech': part_of_speech,
                        'chinese_meaning': row['chinese_meaning'],
                        'example_sentence': row.get('example_sentence', ''),
                        'difficulty_level': int(row.get('difficulty_level', 1))
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
            writer.writerow(['word', 'phonetic_symbol', 'part_of_speech', 'chinese_meaning', 'example_sentence', 'difficulty_level', 'word_order'])
            
            for word in words:
                writer.writerow([
                    word.word_basic.word if word.word_basic else word.word,
                    word.word_basic.phonetic_symbol if word.word_basic else '',
                    word.part_of_speech,
                    word.chinese_meaning,
                    word.example_sentence,
                    word.difficulty_level,
                    word.word_order
                ])
            
            return response
        
        except VocabularyBook.DoesNotExist:
            return Response({"error": "指定的词汇书不存在"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"导出失败: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 