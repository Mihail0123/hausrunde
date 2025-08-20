from datetime import datetime, timezone
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import viewsets, permissions, status
from rest_framework import serializers as rf_serializers
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView as BaseTokenObtainPairView,
    TokenRefreshView as BaseTokenRefreshView,
)
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils.timezone import now
from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, OpenApiResponse, extend_schema_view

from .models import CustomUser
from .serializers import CustomUserSerializer, RegistrationSerializer, LoginSerializer
from ..ads.views import ScopedRateThrottleIsolated


class ThrottledTokenObtainPairView(BaseTokenObtainPairView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth_login'


class ThrottledTokenRefreshView(BaseTokenRefreshView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth_login'


class PublicUserSerializer(rf_serializers.Serializer):
    id = rf_serializers.IntegerField()
    email = rf_serializers.EmailField()
    first_name = rf_serializers.CharField(allow_blank=True, allow_null=True, required=False)
    last_name = rf_serializers.CharField(allow_blank=True, allow_null=True, required=False)
    phone_number = rf_serializers.CharField(allow_blank=True, allow_null=True, required=False)

class RegisterResponseSerializer(rf_serializers.Serializer):
    detail = rf_serializers.CharField()
    user = PublicUserSerializer()

class LoginResponseSerializer(rf_serializers.Serializer):
    detail = rf_serializers.CharField()

class SimpleDetailSerializer(rf_serializers.Serializer):
    detail = rf_serializers.CharField()

class DebugTokenPayloadSerializer(rf_serializers.Serializer):
    has_access = rf_serializers.BooleanField()
    access_expires_in_sec = rf_serializers.IntegerField(allow_null=True)
    access_valid = rf_serializers.BooleanField()
    has_refresh = rf_serializers.BooleanField()
    refresh_expires_in_sec = rf_serializers.IntegerField(allow_null=True)
    refresh_valid = rf_serializers.BooleanField()

@extend_schema(
    summary="Register & set auth cookies",
    request=RegistrationSerializer,
    responses={
        201: OpenApiResponse(
            response=RegisterResponseSerializer,
            description="Account created; JWT tokens are set as httpOnly cookies."
        ),
        400: OpenApiResponse(description="Validation error")},
    tags=["auth"],
)
class RegisterView(CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth_register'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        access_expiry = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
        refresh_expiry = datetime.fromtimestamp(refresh['exp'], tz=timezone.utc)

        data = {
            "detail": "Account created successfully.",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number
            }
        }
        response = Response(data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            key='access_token',
            value=str(access_token),
            httponly=True,
            secure=False,
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


@extend_schema(tags=["users"])
@extend_schema_view(
    list=extend_schema(summary="List users"),
    retrieve=extend_schema(summary="Retrieve user"),
    create=extend_schema(summary="Create user"),
    update=extend_schema(summary="Update user"),
    partial_update=extend_schema(summary="Partial update user"),
    destroy=extend_schema(summary="Delete user"),
)
class CustomUserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]


@extend_schema(tags=["auth"])
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_classes = (ScopedRateThrottleIsolated,)

    def get_throttles(self):
        self.throttle_scope = 'auth_login' if self.request.method == 'POST' else None
        return super().get_throttles()

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(response=LoginSerializer, description="Login form schema")},
        auth=[],
    )
    def get(self, request):
        serializer = self.serializer_class()
        return Response(serializer.data)

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(response=LoginResponseSerializer, description="Login successful; cookies set"),
            401: OpenApiResponse(response=SimpleDetailSerializer, description="Invalid credentials"),
        },
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
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
                secure=False,
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


@extend_schema(
    summary="Logout",
    request=None,
    responses={
        200: OpenApiResponse(response=SimpleDetailSerializer, description="Logged out"),
        401: OpenApiResponse(description="Unauthorized"),
    },
    tags=["auth"],
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        response = Response({"detail": "Logout successful"}, status=status.HTTP_200_OK)
        response.delete_cookie('access_token', path='/')
        response.delete_cookie('refresh_token', path='/')
        return response

@extend_schema(
    summary="Debug token payload",
    request=None,
    responses={200: OpenApiResponse(response=DebugTokenPayloadSerializer)},
    auth=[],
    tags=["auth"],
)
class DebugTokenView(APIView):
    """token info"""
    permission_classes = [AllowAny]
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'auth_debug'

    def get(self, request):
        access_token = request.COOKIES.get('access_token')
        refresh_token = request.COOKIES.get('refresh_token')

        data = {
            "has_access": bool(access_token),
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
                exp = refresh['exp']
                data['refresh_expires_in_sec'] = int(exp - now().timestamp())
                data['refresh_valid'] = True
            except TokenError:
                data['refresh_valid'] = False

        return Response(data)