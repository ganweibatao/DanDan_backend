#!/usr/bin/env python3
import os
import django

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "englishlearning.settings")
django.setup()

from django.contrib.auth.models import User

def set_test_password():
    try:
        user = User.objects.get(username="577542753@qq.com")
        user.set_password("test123")
        user.save()
        print(f"已为用户 {user.username} 设置密码为: test123")
        
        # 验证密码设置成功
        if user.check_password("test123"):
            print("✓ 密码设置成功")
        else:
            print("✗ 密码设置失败")
            
    except User.DoesNotExist:
        print("用户不存在")

if __name__ == "__main__":
    set_test_password() 