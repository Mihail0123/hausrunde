from rest_framework import serializers
from .models import Ad, Booking, AdImage, Review


class AdImageSerializer(serializers.ModelSerializer):
    # Абсолютный URL (с http://127.0.0.1:8000/...), если в контексте есть request
    image_url = serializers.SerializerMethodField()
    # Всегда относительный путь, начинающийся с /media/...
    image_path = serializers.SerializerMethodField()

    class Meta:
        model = AdImage
        fields = ["id", "image", "image_url", "image_path", "caption", "created_at"]
        read_only_fields = ["id", "created_at", "image_url", "image_path"]

    def get_image_url(self, obj):
        try:
            rel = obj.image.url  # '/media/...'
        except Exception:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(rel) if request else rel

    def get_image_path(self, obj):
        try:
            return obj.image.url  # '/media/...'
        except Exception:
            return ""


class AdImageCaptionUpdateSerializer(serializers.ModelSerializer):
    """Allow updating caption only (used by PATCH on single image)."""
    class Meta:
        model = AdImage
        fields = ("caption",)



class AdImageUploadSerializer(serializers.Serializer):
    """
    Not ModelSerializer, to receive:
      - single file to `image`
      - multiple files to `images` (request.FILES.getlist)
    """
    image = serializers.ImageField(required=False, allow_null=True)
    caption = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ReviewSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'ad', 'tenant', 'rating', 'text', 'created_at', 'updated_at')
        read_only_fields = ('id', 'tenant', 'created_at', 'updated_at')

    def validate_rating(self, value):
        if not (1 <= int(value) <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    images = AdImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ad
        fields = [
            "id", "title", "description", "location",
            "price", "rooms", "housing_type",
            "area", "latitude", "longitude",
            "is_active", "is_demo",
            "owner", "created_at", "updated_at",
            "images",
            "average_rating", "reviews_count", "views_count",
        ]
        read_only_fields = [
            "id", "owner", "created_at", "updated_at",
            "images", "average_rating", "reviews_count", "views_count",
        ]


class BookingSerializer(serializers.ModelSerializer):
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Booking
        fields = ("id", "ad", "tenant", "date_from", "date_to", "status", "created_at")
        read_only_fields = ("id", "tenant", "status", "created_at")


class AvailabilityItemSerializer(serializers.Serializer):
    """Public shape for busy date ranges."""
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)
