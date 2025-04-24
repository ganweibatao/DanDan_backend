from django.urls import path
from .views import UserDurationLogListCreateView, UserDurationLogSummaryView, force_report_student_duration

urlpatterns = [
    path('logs/', UserDurationLogListCreateView.as_view(), name='duration-log-list-create'),
    path('logs/summary/', UserDurationLogSummaryView.as_view(), name='duration-log-summary'),
    path('logs/force_report/', force_report_student_duration, name='duration-log-force-report'),
] 