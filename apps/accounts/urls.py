from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, TeacherViewSet, StudentViewSet, send_email_code, verify_email_code, reset_password

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('teachers', TeacherViewSet, basename='teacher')
router.register('students', StudentViewSet, basename='student')

urlpatterns = [
    path('', include(router.urls)),
    path('users/wechat_qrcode/', UserViewSet.as_view({'get': 'wechat_qrcode'})),
    path('users/wechat_callback/', UserViewSet.as_view({'get': 'wechat_callback'})),
    path('email/send-code/', send_email_code, name='send_email_code'),
    path('email/verify-code/', verify_email_code, name='verify_email_code'),
    path('password/reset/', reset_password, name='reset_password'),
]

# No need for: urlpatterns += router.urls 