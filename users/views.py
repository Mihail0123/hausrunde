from datetime import datetime, timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import  AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils.timezone import now

from .models import CustomUser
from .serializers import CustomUserSerializer



# Create your views here.
class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticated]


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, email=email, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            access_expiry = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
            refresh_expiry = datetime.fromtimestamp(refresh['exp'], tz=timezone.utc)

            response = Response({"detail": "Login successful"}, status=status.HTTP_200_OK)
            response.set_cookie(
                key='access_token',
                value=str(access_token),
                httponly=True,
                secure=False, # сменить на True
                samesite='Lax',
                expires=access_expiry,
                path='/',
            )
            response.set_cookie(
                key='refresh_token',
                value=str(refresh),
                httponly=True,
                secure=False,
                samesite='Lax',
                expires=refresh_expiry,
                path='/',
            )
            return response

        return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        response = Response({"detail": "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response


class DebugTokenView(APIView):
    """
    token info
    """
    permission_classes = [AllowAny]

    def get(self, request):
        access_token = request.COOKIES.get('access_token')
        refresh_token = request.COOKIES.get('refresh_token')

        data = {
            "has access": bool(access_token),
            "access_expires_in_sec": None,
            "access_valid": False,
            "has_refresh": bool(refresh_token),
            "refresh_expires_in_sec": None,
            "refresh_valid": False
        }

        if access_token:
            try:
                token = AccessToken(access_token)
                exp = token['exp']
                data['access_expires_in_sec'] = int(exp - now().timestamp())
                data['access_valid'] = True
            except TokenError:
                data['access_valid'] = False

        if refresh_token:
            try:
                refresh = RefreshToken(refresh_token)
                exp = token['exp']
                data['refresh_expires_in_sec'] = int(exp - now().timestamp())
                data['refresh_valid'] = True
            except TokenError:
                data['refresh_valid'] = False

        return Response(data)