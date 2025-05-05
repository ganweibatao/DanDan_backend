from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Teacher, Student

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']
        read_only_fields = ['is_staff']

class TeacherSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    
    class Meta:
        model = Teacher
        fields = ['id', 'user', 'username', 'email', 'avatar', 'bio', 
                 'title', 'specialties', 'university', 'phone_number', 'id_number',
                 'teaching_years', 'teaching_certificate', 'education_level', 'major',
                 'work_status', 'available_time', 'emergency_contact', 
                 'emergency_contact_phone', 'english_level', 'created_at', 'updated_at',
                 'age', 'province', 'city', 'gender']
        read_only_fields = ['user', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        user = instance.user
        user_updated = False

        validated_data.pop('user', None)

        # 兼容平铺 username
        new_username = None
        if 'username' in self.initial_data:
            new_username = self.initial_data['username']
        elif 'username' in validated_data:
            new_username = validated_data.pop('username')
        if new_username is not None and user.username != new_username:
            user.username = new_username
            user_updated = True

        # 兼容平铺 email
        new_email = None
        if 'email' in self.initial_data:
            new_email = self.initial_data['email']
        elif 'email' in validated_data:
            new_email = validated_data.pop('email')
        if new_email is not None and user.email != new_email:
            user.email = new_email
            user_updated = True

        if user_updated:
            user.save()

        for attr, value in validated_data.items():
            if hasattr(instance, attr):
                setattr(instance, attr, value)
        instance.save()
        return instance

class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', required=False, allow_blank=True)
    email = serializers.EmailField(source='user.email', required=False, allow_blank=True)
    real_name = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Student
        fields = ['id', 'user', 'username', 'email', 'avatar', 'bio',
                 'level', 'personality_traits', 'learning_goal',
                 'gender', 'created_at', 'updated_at', 'age', 'province', 'city', 'grade', 'phone_number',
                 'real_name']
        read_only_fields = ['created_at', 'updated_at']

    def update(self, instance, validated_data):
        user = instance.user
        user_updated = False

        validated_data.pop('user', None)

        print("[StudentSerializer.update] before update: user.username =", user.username)

        # 兼容平铺 username
        new_username = None
        if 'username' in self.initial_data:
            new_username = self.initial_data['username']
        elif 'username' in validated_data:
            new_username = validated_data.pop('username')
        if new_username is not None:
            print("[StudentSerializer.update] new_username from payload:", new_username)
            if user.username != new_username:
                user.username = new_username
                user_updated = True

        # 兼容平铺 email
        new_email = None
        if 'email' in self.initial_data:
            new_email = self.initial_data['email']
        elif 'email' in validated_data:
            new_email = validated_data.pop('email')
        if new_email is not None:
            print("[StudentSerializer.update] new_email from payload:", new_email)
            if user.email != new_email:
                user.email = new_email
                user_updated = True

        if user_updated:
            print("[StudentSerializer.update] saving user, new username:", user.username, ", new email:", user.email)
            user.save()
            print("[StudentSerializer.update] after save: user.username =", user.username, ", user.email =", user.email)
        else:
            print("[StudentSerializer.update] user not updated, no changes detected.")

        for attr, value in validated_data.items():
            if hasattr(instance, attr):
                setattr(instance, attr, value)
        instance.save()
        return instance 