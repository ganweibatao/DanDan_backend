from django.db import models
from django.contrib.auth.models import User

# 在文件顶部定义GENDER_CHOICES，供Teacher和Student共用
GENDER_CHOICES = [
    ('male', '男'),
    ('female', '女'),
    ('other', '其他'),
]

class Profile(models.Model):
    """用户公共信息"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class Teacher(Profile):
    """教师信息"""
    WORK_STATUS_CHOICES = [
        ('full_time', '全职'),
        ('part_time', '兼职'),
        ('freelance', '自由职业'),
    ]
    
    EDUCATION_LEVEL_CHOICES = [
        ('bachelor', '学士'),
        ('master', '硕士'),
        ('phd', '博士'),
        ('other', '其他'),
    ]
    
    ENGLISH_LEVEL_CHOICES = [
        ('cet4', 'CET-4'),
        ('cet6', 'CET-6'),
        ('ielts', 'IELTS'),
        ('toefl', 'TOEFL'),
        ('professional', '专业英语'),
        ('native', '母语'),
        ('other', '其他'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    title = models.CharField(max_length=100, blank=True)  # 职称
    specialties = models.CharField(max_length=200, blank=True)  # 专长领域
    university = models.CharField(max_length=200, blank=True)  # 毕业院校
    phone_number = models.CharField(max_length=20, blank=True)  # 电话号码
    id_number = models.CharField(max_length=18, blank=True)  # 身份证号
    teaching_years = models.PositiveIntegerField(default=0)  # 教学年限
    teaching_certificate = models.CharField(max_length=100, blank=True)  # 教师资格证编号
    education_level = models.CharField(max_length=50, choices=EDUCATION_LEVEL_CHOICES, blank=True)  # 最高学历
    major = models.CharField(max_length=100, blank=True)  # 专业方向
    work_status = models.CharField(max_length=50, choices=WORK_STATUS_CHOICES, blank=True)  # 工作状态
    available_time = models.TextField(blank=True)  # 可授课时间段
    emergency_contact = models.CharField(max_length=100, blank=True)  # 紧急联系人
    emergency_contact_phone = models.CharField(max_length=20, blank=True)  # 紧急联系人电话
    english_level = models.CharField(max_length=50, choices=ENGLISH_LEVEL_CHOICES, blank=True)  # 英语水平
    age = models.PositiveIntegerField(null=True, blank=True)  # 年龄
    province = models.CharField(max_length=50, blank=True)  # 省份
    city = models.CharField(max_length=50, blank=True)  # 城市
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)  # 性别
    
    def __str__(self):
        return f"Teacher: {self.user.username}"

class Student(Profile):
    """学生信息"""
    ENGLISH_LEVEL_CHOICES = [
        ('beginner', '初级'),
        ('intermediate', '中级'),
        ('advanced', '高级'),
        ('proficient', '精通'),
    ]
    
    GRADE_CHOICES = [
        ('primary_1', '小学一年级'),
        ('primary_2', '小学二年级'),
        ('primary_3', '小学三年级'),
        ('primary_4', '小学四年级'),
        ('primary_5', '小学五年级'),
        ('primary_6', '小学六年级'),
        ('junior_1', '初中一年级'),
        ('junior_2', '初中二年级'),
        ('junior_3', '初中三年级'),
        ('senior_1', '高中一年级'),
        ('senior_2', '高中二年级'),
        ('senior_3', '高中三年级'),
        ('college_1', '大学一年级'),
        ('college_2', '大学二年级'),
        ('college_3', '大学三年级'),
        ('college_4', '大学四年级'),
        ('graduate', '研究生'),
        ('other', '其他'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    real_name = models.CharField(max_length=50, blank=True, verbose_name='真实姓名')
    level = models.CharField(max_length=50, choices=ENGLISH_LEVEL_CHOICES, blank=True)  # 英语水平
    personality_traits = models.CharField(max_length=200, blank=True, verbose_name='性格特点')  # 性格特点
    learning_goal = models.TextField(blank=True)  # 学习目标
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)  # 性别
    age = models.PositiveIntegerField(null=True, blank=True)  # 年龄
    province = models.CharField(max_length=50, blank=True)  # 省份
    city = models.CharField(max_length=50, blank=True)  # 城市
    grade = models.CharField(max_length=20, choices=GRADE_CHOICES, blank=True)  # 年级
    phone_number = models.CharField(max_length=20, blank=True, verbose_name='电话号码') # 学生电话号码
    
    def __str__(self):
        return f"Student: {self.user.username}"

class StudentTeacherRelationship(models.Model):
    """学生-教师关系表"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='teacher_relationships')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='student_relationships')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['student', 'teacher']
        
    def __str__(self):
        return f"{self.student.user.username} - {self.teacher.user.username}" 