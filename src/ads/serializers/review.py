from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from django.utils import timezone

from src.ads.serializers.common import PublicUserTinySerializer
from src.ads.models import Review, Booking


class ReviewSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(source="text", required=False, allow_blank=True)

    class Meta:
        model = Review
        fields = "__all__"
        read_only_fields = ("tenant", "ad")

    def validate(self, attrs):
        """
        For CREATE we allow missing `booking` (perform_create resolves by `ad`).
        For UPDATE or when `booking` is provided, enforce integrity checks here.
        """
        request = self.context["request"]
        user = request.user
        booking = attrs.get("booking")
        ad = attrs.get("ad")

        if booking is None and self.instance is None:
            return attrs

        if booking and booking.tenant_id != user.id:
            raise serializers.ValidationError({"booking": "Only the tenant can review this booking."})

        if booking and booking.status != Booking.CONFIRMED:
            raise serializers.ValidationError({"booking": "Only CONFIRMED bookings can be reviewed."})
        if booking and timezone.localdate() < booking.date_to:
            raise serializers.ValidationError({"booking": "You can review only after the stay has ended."})

        if booking and ad and booking.ad_id != ad.id:
            raise serializers.ValidationError({"ad": "Booking does not belong to this ad."})

        if booking and Review.objects.filter(booking=booking).exists():
            raise serializers.ValidationError({"booking": "This booking is already reviewed."})

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        booking = validated_data["booking"]
        validated_data["tenant"] = request.user
        validated_data["ad"] = booking.ad
        return super().create(validated_data)

    def update(self, instance, validated_data):
        new_ad = validated_data.get("ad")
        if new_ad is not None and new_ad.id != instance.ad_id:
            raise serializers.ValidationError({"ad": "Cannot change ad for an existing review."})
        if "booking" in validated_data and validated_data["booking"].id != instance.booking_id:
            raise serializers.ValidationError({"booking": "Cannot change booking for an existing review."})
        return super().update(instance, validated_data)
