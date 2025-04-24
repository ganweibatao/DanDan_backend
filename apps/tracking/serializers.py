from rest_framework import serializers
from .models import UserDurationLog

class UserDurationLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = UserDurationLog
        fields = ['id', 'user', 'type', 'duration', 'client_start_time', 'client_end_time', 'created_at']
        read_only_fields = ['id', 'user', 'created_at'] 