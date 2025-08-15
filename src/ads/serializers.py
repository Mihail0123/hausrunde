from rest_framework import serializers
from .models import Ad, Booking

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


class BookingSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = ('id', 'ad', 'tenant', 'date_from', 'date_to', 'status', 'created_at')
        read_only_fields = ('id', 'tenant', 'status', 'created_at')

    def validate(self, attrs):
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from must be <= date_to.")
        return attrs