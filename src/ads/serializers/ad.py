from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from src.ads.models import Ad, Review
from .common import ReviewShortSerializer
from .ad_image import AdImageSerializer


class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    images = AdImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)
    housing_type = serializers.ChoiceField(choices=Ad.HousingType.choices)
    recent_reviews = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Ad
        fields = [
            "id", "title", "description", "location",
            "price", "rooms", "housing_type",
            "area", "latitude", "longitude",
            "is_active", "is_demo",
            "owner", "owner_id",
            "created_at", "updated_at",
            "images",
            "average_rating", "reviews_count", "views_count",
            "recent_reviews",
        ]
        read_only_fields = [
            "id", "owner", "owner_id",
            "created_at", "updated_at",
            "images", "average_rating", "reviews_count", "views_count",
            "recent_reviews",
        ]

    @extend_schema_field(ReviewShortSerializer(many=True))
    def get_recent_reviews(self, obj):
        """
        Return last 3 reviews with rating/comment and tenant email.
        """
        qs = (Review.objects
              .filter(ad=obj)
              .select_related("tenant")
              .order_by("-created_at")[:3])
        out = []
        for r in qs:
            out.append({
                "id": r.id,
                "rating": r.rating,
                "comment": r.text,
                "tenant": {"id": r.tenant_id, "email": getattr(r.tenant, "email", None)},
                "created_at": r.created_at,
            })
        return out

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Price must be >= 0.")
        return value

    def validate_rooms(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Rooms must be >= 0.")
        return value

    def validate_area(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Area must be >= 0.")
        return value

    def validate_latitude(self, value):
        if value is not None:
            try:
                v = float(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError("Latitude must be a number.")
            if not (-90.0 <= v <= 90.0):
                raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if value is not None:
            try:
                v = float(value)
            except (TypeError, ValueError):
                raise serializers.ValidationError("Longitude must be a number.")
            if not (-180.0 <= v <= 180.0):
                raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def validate(self, attrs):
        """
        On create: require both coordinates (map pin).
        On update: allow partial coordinate updates.
        """
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lon = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if self.instance is None and (lat is None or lon is None):
            raise serializers.ValidationError(
                {"detail": "Set the map pin to provide latitude and longitude."}
            )
        return attrs

