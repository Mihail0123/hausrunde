from datetime import datetime, timezone
from django.utils.timezone import now
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError

class JWTAuthCookieMiddleware:
    """
    Get JWT from httpOnly cookies and (if needed) inject into Authorization header.
    If access is expired but refresh is valid, auto-issue a new access token and set cookie.
    IMPORTANT: Do NOT override an explicit Authorization header provided by the client.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Respect explicit Authorization header from client (e.g., API explorer, tests)
        if request.META.get('HTTP_AUTHORIZATION'):
            return self.get_response(request)

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
                access_token = None  # token expired, try refresh

        if not access_token and refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                new_access = refresh.access_token
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {str(new_access)}'

                access_expiry = datetime.fromtimestamp(new_access['exp'], tz=timezone.utc)
                response = self.get_response(request)
                response.set_cookie(
                    key='access_token',
                    value=str(new_access),
                    httponly=True,
                    secure=getattr(settings, 'AUTH_COOKIE_SECURE', not settings.DEBUG),
                    samesite=getattr(settings, 'AUTH_COOKIE_SAMESITE', 'Lax'),
                    expires=access_expiry,
                    path=getattr(settings, 'AUTH_COOKIE_PATH', '/'),
                    domain=getattr(settings, 'AUTH_COOKIE_DOMAIN', None),
                )
                return response
            except TokenError:
                pass

        if not response:
            response = self.get_response(request)

        return response
