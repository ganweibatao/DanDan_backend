from rest_framework import serializers
from .models import UserDurationLog
from apps.accounts.models import Student

class UserDurationLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    student_name = serializers.StringRelatedField(source='student', read_only=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=Student.objects.all(), 
        allow_null=True, 
        required=False,
        write_only=True
    )

    class Meta:
        model = UserDurationLog
        fields = ['id', 'user', 'student', 'student_name', 'type', 'duration', 'client_start_time', 'client_end_time', 'created_at']
        read_only_fields = ['id', 'user', 'created_at'] 