from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class CookieTokenAuthentication(TokenAuthentication):
    """
    Extends TokenAuthentication to support reading the token from an HttpOnly cookie.
    """
    def authenticate(self, request):
        # Check if 'auth_token' cookie is present
        token = request.COOKIES.get('auth_token')

        if not token:
            # If no cookie, fallback to standard Authorization header authentication
            # This allows using the same API endpoint for browser sessions (cookie)
            # and other clients (e.g., mobile apps) that might use the header.
            # If you *only* want cookie auth, remove the call to super().authenticate()
            # and just return None here.
            return super().authenticate(request)
            # Alternatively, if you want ONLY cookie auth:
            # return None 

        # Authenticate using the token found in the cookie
        try:
            return self.authenticate_credentials(token)
        except AuthenticationFailed as e:
            # You might want to log the failed attempt here
            raise e 