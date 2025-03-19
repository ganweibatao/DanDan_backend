from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Word, Course
from .serializers import CategorySerializer, WordSerializer, CourseSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    """
    API端点，允许单词分类查看或编辑
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

class WordViewSet(viewsets.ModelViewSet):
    """
    API端点，允许单词查看或编辑
    """
    queryset = Word.objects.all()
    serializer_class = WordSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'difficulty_level']
    search_fields = ['word', 'definition', 'example']
    ordering_fields = ['word', 'difficulty_level', 'created_at']
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """按分类获取单词"""
        category_id = request.query_params.get('category_id')
        if category_id:
            words = Word.objects.filter(category_id=category_id)
            serializer = self.get_serializer(words, many=True)
            return Response(serializer.data)
        return Response({"error": "请提供category_id参数"}, status=400)

class CourseViewSet(viewsets.ModelViewSet):
    """
    API端点，允许课程查看或编辑
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['teacher', 'category', 'difficulty_level', 'is_active']
    search_fields = ['title', 'description']
    ordering_fields = ['title', 'difficulty_level', 'created_at']
    
    @action(detail=True, methods=['get'])
    def words(self, request, pk=None):
        """获取课程的所有单词"""
        course = self.get_object()
        words = course.words.all()
        serializer = WordSerializer(words, many=True)
        return Response(serializer.data) 