"""
URL configuration for englishlearning project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import logging
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from apps.accounts.views import UserViewSet
# from rest_framework.documentation import include_docs_urls

# 测试日志配置是否生效
logger = logging.getLogger('django')
logger.info('测试日志配置 - 这条信息应该出现在django.log文件中')

# API版本
API_PREFIX = 'api/v1/'

# API文档配置
schema_view = get_schema_view(
   openapi.Info(
      title="英语学习系统 API",
      default_version='v1',
      description="英语学习系统的API文档",
      terms_of_service="https://www.yourapp.com/terms/",
      contact=openapi.Contact(email="contact@yourapp.com"),
      license=openapi.License(name="Your License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # REST Framework浏览器API
    path('api-auth/', include('rest_framework.urls')),
    
    # API文档
    # path('docs/', include_docs_urls(title='English Learning API')),
    
    # social-auth-app-django URLs
    path('auth/', include('social_django.urls', namespace='social')),
    
    # 微信登录回调路由
    path('callback/weixin/', UserViewSet.as_view({'get': 'wechat_callback'}), name='weixin-callback'),
    
    # 应用API路由
    path(f'{API_PREFIX}accounts/', include('apps.accounts.urls')),
    path(f'{API_PREFIX}vocabulary/', include('apps.vocabulary.urls')),
    path(f'{API_PREFIX}learning/', include('apps.learning.urls')),
    path(f'{API_PREFIX}tracking/', include('apps.tracking.urls')),
    
    # API 文档
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# 开发环境中提供媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
