from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    VocabularyBookViewSet, BookWordViewSet, 
    BookWordBatchQueryView,
    StudentKnownWordViewSet,
    ProxyYoudaoPronunciationView
)

router = DefaultRouter()
router.register(r'books', VocabularyBookViewSet, basename='vocabularybook')
router.register(r'book-words', BookWordViewSet, basename='bookword')

router.register(r'known-words', StudentKnownWordViewSet, basename='studentknownword')

urlpatterns = [
    path('', include(router.urls)),
    # 词库书籍相关 - 下面的规则与router中的规则重复，应删除，以便ViewSet中的action可以正常工作
    # path('books/', views.VocabularyBookListView.as_view(), name='vocabulary-book-list'),
    # path('books/<int:pk>/', views.VocabularyBookDetailView.as_view(), name='vocabulary-book-detail'),
    path('books/<int:book_id>/words/', views.BookWordListView.as_view(), name='book-word-list'),
    path('books/<int:book_id>/words/batch/', views.BookWordBatchQueryView.as_view(), name='book-word-batch'),
    
    # 单词相关
    path('words/<int:pk>/', views.BookWordDetailView.as_view(), name='book-word-detail'),
    path('words/search/', views.WordSearchView.as_view(), name='word-search'),
    path('words/basic/', views.WordBasicListView.as_view(), name='word-basic-list'),


    
    # 学生自定义相关

    
    # 导入/导出
    path('books/<int:book_id>/import/', views.ImportWordsView.as_view(), name='import-words'),
    path('books/<int:book_id>/export/', views.ExportWordsView.as_view(), name='export-words'),
    # iciba suggest
    path('iciba_suggest/', views.iciba_suggest, name='iciba-suggest'),
    
    # 发音代理
    path('pronunciation/proxy/', ProxyYoudaoPronunciationView.as_view(), name='pronunciation-proxy'),
] 