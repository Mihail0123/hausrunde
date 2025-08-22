from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions as django_exc

from .models import CustomUser


class RegistrationSerializer(serializers.ModelSerializer):
    """Registration payload -> creates a user and hashes password."""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=32)


    class Meta:
        model = CustomUser
        fields = ('email', 'password', 'first_name', 'last_name', 'phone_number')

    def validate_password(self, value):
        """Run Django's password validators (AUTH_PASSWORD_VALIDATORS)."""
        try:
            validate_password(value)
        except django_exc.ValidationError as e:
            # Return list of readable error messages
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        user = CustomUser.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', '')
        )
        return user


class CustomUserSerializer(serializers.ModelSerializer):
    """Representation of a user; staff/active are read-only for API clients."""
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=32)


    class Meta:
        model = CustomUser
        fields = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'is_active', 'is_staff')
        read_only_fields = ('id', 'is_active', 'is_staff')


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
