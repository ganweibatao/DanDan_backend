from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, TeacherViewSet, StudentViewSet

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')
router.register('teachers', TeacherViewSet, basename='teacher')
router.register('students', StudentViewSet, basename='student')

urlpatterns = [
    path('', include(router.urls)),
]

# No need for: urlpatterns += router.urls 