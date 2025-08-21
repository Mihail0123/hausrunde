from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes
from datetime import date

from .models import Ad, Booking, AdImage, Review


class AdImageSerializer(serializers.ModelSerializer):
    # Absolute URL (с http://127.0.0.1:8000/...), if request in context
    image_url = serializers.SerializerMethodField()
    # Relative /media/...
    image_path = serializers.SerializerMethodField()

    class Meta:
        model = AdImage
        fields = ["id", "image", "image_url", "image_path", "caption", "created_at"]
        read_only_fields = ["id", "created_at", "image_url", "image_path"]

    @extend_schema_field(OpenApiTypes.STR)
    def get_image_url(self, obj) -> str:
        try:
            rel = obj.image.url
        except Exception:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(rel) if request else rel

    @extend_schema_field(OpenApiTypes.STR)
    def get_image_path(self, obj) -> str:
        try:
            return obj.image.url
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
    # Read-only author name for convenience
    tenant = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        # booking is not exposed in the public API; we bind it server-side
        fields = ('id', 'ad', 'tenant', 'rating', 'text', 'created_at', 'updated_at')
        read_only_fields = ('id', 'tenant', 'created_at', 'updated_at')

    def validate_rating(self, value):
        # Keep server-side validation strict
        v = int(value)
        if not (1 <= v <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return v



class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
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
            "owner", "owner_id",
            "created_at", "updated_at",
            "images",
            "average_rating", "reviews_count", "views_count",
        ]
        read_only_fields = [
            "id", "owner", "owner_id",
            "created_at", "updated_at",
            "images", "average_rating", "reviews_count", "views_count",
        ]

    # --- Server-side validation (non-negative numbers and lat/lon ranges) ---
    def validate_price(self, value):
        # Accept None; otherwise require non-negative
        if value is not None and value < 0:
            raise serializers.ValidationError("Price must be >= 0.")
        return value

    def validate_rooms(self, value):
        # Accept None; otherwise require non-negative integer
        if value is not None and value < 0:
            raise serializers.ValidationError("Rooms must be >= 0.")
        return value

    def validate_area(self, value):
        # Accept None; otherwise require non-negative
        if value is not None and value < 0:
            raise serializers.ValidationError("Area must be >= 0.")
        return value

    def validate_latitude(self, value):
        # Accept None; otherwise require -90..90
        if value is not None:
            v = float(value)
            if not (-90.0 <= v <= 90.0):
                raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        # Accept None; otherwise require -180..180
        if value is not None:
            v = float(value)
            if not (-180.0 <= v <= 180.0):
                raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value


class BookingSerializer(serializers.ModelSerializer):
    # Writable input: `ad`, `date_from`, `date_to`
    # Read-only denormalized fields for UI convenience:
    ad_id = serializers.IntegerField(read_only=True)
    ad_title = serializers.CharField(source="ad.title", read_only=True)

    # Tenant/Owner as objects {id, email} for cards/tables
    tenant = serializers.SerializerMethodField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)

    # Action flags based on current user role (tenant/owner) and status
    can_cancel = serializers.SerializerMethodField(read_only=True)
    can_cancel_quote = serializers.SerializerMethodField(read_only=True)
    can_confirm = serializers.SerializerMethodField(read_only=True)
    can_reject = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "ad",              # input
            "ad_id", "ad_title",
            "tenant", "owner",
            "date_from", "date_to",
            "status", "created_at",
            "can_cancel", "can_cancel_quote", "can_confirm", "can_reject",
        )
        read_only_fields = (
            "id", "tenant", "owner",
            "ad_id", "ad_title",
            "status", "created_at",
            "can_cancel", "can_cancel_quote", "can_confirm", "can_reject",
        )

    # -------------------------
    # Validation (server-side)
    # -------------------------
    def validate(self, data):
        """
        Global validation for booking create/update:
        - required fields
        - `date_from` >= tomorrow; `date_to` > `date_from`
        - ad must be active
        - tenant cannot book own ad
        - no overlaps with existing PENDING/CONFIRMED
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)

        ad = data.get("ad") or getattr(self.instance, "ad", None)
        date_from = data.get("date_from") or getattr(self.instance, "date_from", None)
        date_to = data.get("date_to") or getattr(self.instance, "date_to", None)

        errors = {}

        # Required fields
        if not ad:
            errors["ad"] = "This field is required."
        if not date_from:
            errors["date_from"] = "This field is required."
        if not date_to:
            errors["date_to"] = "This field is required."
        if errors:
            raise serializers.ValidationError(errors)

        # Chronology rules
        today = date.today()
        if date_from <= today:
            errors["date_from"] = "Must be at least tomorrow."
        if date_to <= date_from:
            errors["date_to"] = "Must be greater than date_from."

        # Ad must be active
        if ad and not getattr(ad, "is_active", True):
            errors.setdefault("ad", "This ad is inactive and cannot be booked.")

        # Forbid booking own ad
        if user and getattr(ad, "owner_id", None) == getattr(user, "id", None):
            errors.setdefault("non_field_errors", []).append("You cannot book your own ad.")

        # Prevent overlaps with existing CONFIRMED
        if ad and date_from and date_to:
            qs = Booking.objects.filter(
                ad=ad,
                status=Booking.CONFIRMED,
                date_from__lt=date_to,
                date_to__gt=date_from,
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                errors.setdefault("non_field_errors", []).append(
                    "Selected dates overlap with an confirmed booking."
                )

        if errors:
            raise serializers.ValidationError(errors)
        return data

    # -------------------------
    # Presentation helpers
    # -------------------------
    def get_tenant(self, obj):
        t = getattr(obj, "tenant", None)
        if not t:
            return None
        return {"id": t.id, "email": t.email}

    def get_owner(self, obj):
        ad = getattr(obj, "ad", None)
        if not ad or not getattr(ad, "owner", None):
            return None
        return {"id": ad.owner.id, "email": ad.owner.email}

    # Role helpers
    def _is_tenant(self, obj, user):
        return bool(user and obj.tenant_id == getattr(user, "id", None))

    def _is_owner(self, obj, user):
        ad_owner_id = getattr(getattr(obj, "ad", None), "owner_id", None)
        return bool(user and ad_owner_id == getattr(user, "id", None))

    # Action flags
    def get_can_cancel(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        return self._is_tenant(obj, user) and obj.status in (Booking.PENDING, Booking.CONFIRMED)

    def get_can_cancel_quote(self, obj):
        # Tenant can preview cancel-quote for PENDING or CONFIRMED (matches /cancel-quote/ view).
        user = getattr(self.context.get("request"), "user", None)
        return self._is_tenant(obj, user) and obj.status in (Booking.PENDING, Booking.CONFIRMED)

    def get_can_confirm(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        return self._is_owner(obj, user) and obj.status == Booking.PENDING

    def get_can_reject(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        return self._is_owner(obj, user) and obj.status == Booking.PENDING


class AvailabilityItemSerializer(serializers.Serializer):
    """Public shape for busy date ranges."""
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)
