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
    word_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    wrong_word_count = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    class Meta:
        model = UserDurationLog
        fields = [
            'id', 'user', 'student', 'student_name',
            'type', 'duration', 'word_count', 'wrong_word_count',
            'client_start_time', 'client_end_time', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'created_at'] 