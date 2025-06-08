from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

class CookieTokenAuthentication(TokenAuthentication):
    """
    从Cookie中获取Token的认证类
    """
    def authenticate(self, request):
        # 首先尝试从header中获取token
        auth = super().authenticate(request)
        if auth is not None:
            return auth
            
        # 如果header中没有，则尝试从cookie中获取
        token = request.COOKIES.get('auth_token')
        if token:
            try:
                token_obj = Token.objects.get(key=token)
                return (token_obj.user, token_obj)
            except Token.DoesNotExist:
                return None
        
        return None 