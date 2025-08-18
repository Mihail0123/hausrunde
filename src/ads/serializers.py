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
        ad = attrs.get('ad')

        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError("date_from must be <= date_to.")

        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            if ad and ad.owner_id == request.user.id:
                raise serializers.ValidationError("You cannot book your own ad.")

        if ad and not ad.is_active:
            raise serializers.ValidationError("Cannot book an inactive ad.")

        if ad and date_from and date_to:
            overlap_exists = Booking.objects.filter(
                ad=ad,
                status__in=['PENDING', 'CONFIRMED'],
                date_from__lte=date_to,
                date_to__gte=date_from
            ).exists()
            if overlap_exists:
                raise serializers.ValidationError("This ad is already booked for the selected dates.")

        return attrs