from rest_framework import serializers
from .models import Ad, Booking, AdImage, Review


class AdImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdImage
        fields = ["id", "image", "caption", "created_at"]
        read_only_fields = ["id", "created_at"]

class AdImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdImage
        fields = ["image", "caption"]


class ReviewSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "tenant", "rating", "text", "created_at"]
        read_only_fields = ["id", "tenant", "created_at"]


class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    images = AdImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)  # получаем из annotate()

    class Meta:
        model = Ad
        fields = [
            "id", "title", "description", "location",
            "price", "rooms", "housing_type",
            "area", "latitude", "longitude",
            "is_active", "is_demo",
            "owner", "created_at", "updated_at",
            "images",
            "average_rating",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at", "images", "average_rating"]


class BookingSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = ("id", "ad", "tenant", "date_from", "date_to", "status", "created_at")
        read_only_fields = ("id", "tenant", "status", "created_at")
