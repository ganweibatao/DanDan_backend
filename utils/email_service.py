# -*- coding: utf-8 -*-

import json
import logging
import datetime
from concurrent.futures import ThreadPoolExecutor
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.ses.v20201002 import ses_client, models
from django.conf import settings

# 获取日志记录器
logger = logging.getLogger('django')

# 创建线程池，用于异步发送邮件
_email_executor = ThreadPoolExecutor(max_workers=4)

class EmailService:
    """腾讯云邮件服务工具类"""
    
    @staticmethod
    def send_verification_code(email, code):
        """
        发送验证码邮件（异步）
        
        Args:
            email: 收件人邮箱
            code: 验证码
        
        Returns:
            Future对象
        """
        return _email_executor.submit(
            EmailService._send_verification_code_sync, 
            email, 
            code
        )
    
    @staticmethod
    def _send_verification_code_sync(email, code):
        """
        同步发送验证码邮件
        
        Args:
            email: 收件人邮箱
            code: 验证码
            
        Returns:
            bool: 发送是否成功
        """
        try:
            # 实例化一个认证对象
            cred = credential.Credential(
                settings.TENCENT_CLOUD_SECRET_ID,
                settings.TENCENT_CLOUD_SECRET_KEY
            )
            
            # 实例化http选项
            httpProfile = HttpProfile()
            httpProfile.endpoint = "ses.tencentcloudapi.com"
            
            # 实例化client选项
            clientProfile = ClientProfile()
            clientProfile.httpProfile = httpProfile
            
            # 实例化SES客户端
            client = ses_client.SesClient(cred, settings.TENCENT_CLOUD_REGION, clientProfile)
            
            # 实例化请求对象
            req = models.SendEmailRequest()
            params = {
                "FromEmailAddress": settings.EMAIL_FROM,
                "Destination": [email],
                "Subject": "邮箱验证码",
                "Template": {
                    "TemplateID": settings.EMAIL_TEMPLATE_ID,
                    "TemplateData": json.dumps({"code": code})
                }
            }
            req.from_json_string(json.dumps(params))
            
            # 发送请求
            resp = client.SendEmail(req)
            
            # 记录成功日志
            logger.info(f"邮件发送成功: {email}, 验证码: {code}")
            logger.debug(f"邮件发送响应: {resp.to_json_string()}")
            
            return True
            
        except TencentCloudSDKException as err:
            # 记录错误日志
            logger.error(f"邮件发送失败: {email}, 错误: {err}")
            return False
        except Exception as e:
            # 记录未预期异常
            logger.error(f"邮件发送出现未预期异常: {email}, 异常: {e}")
            return False 