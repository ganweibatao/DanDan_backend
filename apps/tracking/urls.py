from django.urls import path
from .views import (
    UserDurationLogListCreateView,
    UserDurationLogSummaryView,
    TeacherDailyTeachingDurationView,
)

urlpatterns = [
    path('logs/', UserDurationLogListCreateView.as_view(), name='user-duration-log-list-create'),
    path('logs/summary/', UserDurationLogSummaryView.as_view(), name='user-duration-summary'),
    path('teacher/daily_teaching_duration/', TeacherDailyTeachingDurationView.as_view(), name='teacher-daily-teaching-duration'),
] 