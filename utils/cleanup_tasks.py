# -*- coding: utf-8 -*-

import logging
from django.utils import timezone
from apps.accounts.models import EmailVerificationCode

# 获取日志记录器
logger = logging.getLogger('django')

def cleanup_verification_codes():
    """
    清理邮箱验证码定时任务
    - 删除所有已使用的验证码
    - 删除所有已过期的验证码
    
    Returns:
        int: 清理的记录总数
    """
    try:
        # 删除已使用的验证码
        used_deleted, _ = EmailVerificationCode.objects.filter(
            is_used=True
        ).delete()
        
        # 删除已过期的验证码
        expired_deleted, _ = EmailVerificationCode.objects.filter(
            is_used=False,
            expires_at__lt=timezone.now()
        ).delete()
        
        total_deleted = used_deleted + expired_deleted
        
        # 记录清理结果
        logger.info(f"验证码清理任务执行完成: 共清理 {total_deleted} 条记录 (已使用: {used_deleted}, 已过期: {expired_deleted})")
        
        return total_deleted
        
    except Exception as e:
        logger.error(f"验证码清理任务执行出错: {e}")
        return 0 