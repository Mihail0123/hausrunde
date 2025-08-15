from django.utils.timezone import now
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError

class JWTAuthCookieMiddleware:
    """
    mw to get JWT token from cookies to Auth header
    auto updates access with refresh token
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        access_token = request.COOKIES.get('access_token')
        refresh_token = request.COOKIES.get('refresh_token')
        response = None

        if access_token:
            try:
                token = AccessToken(access_token)
                if token['exp'] < now().timestamp():
                    raise TokenError("Access token expired")
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
            except TokenError:
                access_token = None # token expired, try refresh

        if not access_token and refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                new_access = refresh.access_token
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {str(new_access)}'

                response = self.get_response(request)
                response.set_cookie(
                    key='access_token',
                    value=str(new_access),
                    httponly=True,
                    secure=False,
                    samesite='Lax',
                    path='/',
                    expires=new_access['exp'],
                )
                return response
            except TokenError:
                pass

        if not response:
            response = self.get_response(request)

        return response
