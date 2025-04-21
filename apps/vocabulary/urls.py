from django.urls import path
from . import views

urlpatterns = [
    # 词库书籍相关
    path('books/', views.VocabularyBookListView.as_view(), name='vocabulary-book-list'),
    path('books/<int:pk>/', views.VocabularyBookDetailView.as_view(), name='vocabulary-book-detail'),
    path('books/<int:book_id>/words/', views.BookWordListView.as_view(), name='book-word-list'),
    
    # 单词相关
    path('words/<int:pk>/', views.BookWordDetailView.as_view(), name='book-word-detail'),
    path('words/search/', views.WordSearchView.as_view(), name='word-search'),
    path('words/basic/', views.WordBasicListView.as_view(), name='word-basic-list'),
    path('words/user/<int:word_basic_id>/', views.UserWordView.as_view(), name='user-word'),
    path('words/customization/', views.WordCustomizationListView.as_view(), name='word-customization-list'),
    
    # 学生自定义相关
    path('customizations/', views.StudentCustomizationListView.as_view(), name='student-customization-list'),
    path('customizations/<int:pk>/', views.StudentCustomizationDetailView.as_view(), name='student-customization-detail'),
    
    # 导入/导出
    path('books/<int:book_id>/import/', views.ImportWordsView.as_view(), name='import-words'),
    path('books/<int:book_id>/export/', views.ExportWordsView.as_view(), name='export-words'),
    # iciba suggest
    path('iciba_suggest/', views.iciba_suggest, name='iciba-suggest'),
] 