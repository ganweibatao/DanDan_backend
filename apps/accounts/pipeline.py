from rest_framework.authtoken.models import Token
import logging

logger = logging.getLogger('django')

def set_auth_cookie(backend, user, response, *args, **kwargs):
    """在社交登录完成后设置auth_token到cookie"""
    logger.info(f"设置auth_token cookie给用户: {user.username if user else 'None'}")
    
    if user and hasattr(response, 'set_cookie'):
        token, _ = Token.objects.get_or_create(user=user)
        response.set_cookie(
            key='auth_token',
            value=token.key,
            httponly=True,
            samesite='Lax',
            max_age=60*60*24*30,  # 30天
            path='/'
        )
        logger.info(f"已为用户{user.username}设置auth_token cookie: {token.key[:8]}...")
    
    return {'token': token.key if user else None} 