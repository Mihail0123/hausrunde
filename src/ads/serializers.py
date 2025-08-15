from rest_framework import serializers
from .models import Ad

class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Ad
        fields = [
            'id', 'title', 'description', 'location', 'price',
            'rooms', 'housing_type', 'is_active', 'owner',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'created_at', 'updated_at']