from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes
from datetime import date
from django.utils import timezone

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
    Supports either a single 'image' or multiple 'images' files.
    View will read request.FILES.getlist('images'); this serializer only
    documents the shape for OpenAPI and enforces "at least one file".
    """
    image = serializers.ImageField(required=False)
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    caption = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs):
        request = self.context.get('request')
        # Accept if single 'image' provided…
        if attrs.get('image'):
            return attrs
        # …or if any files came as 'images'
        files = []
        if request is not None:
            files = request.FILES.getlist('images')
        images = attrs.get('images') or files
        if not images:
            raise serializers.ValidationError({'images': 'Provide at least one image.'})
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(source="text", required=False, allow_blank=True)
    class Meta:
        model = Review
        fields = "__all__"
        read_only_fields = ("tenant", "ad")  # tenant is always request.user

    def validate(self, attrs):
        """
        For CREATE we allow missing `booking` (perform_create resolves by `ad`).
        For UPDATE or when `booking` is provided, enforce integrity checks here.
        """
        request = self.context["request"]
        user = request.user
        booking = attrs.get("booking")
        ad = attrs.get("ad")

        # CREATE without booking is allowed — perform_create will find booking by `ad`
        if booking is None and self.instance is None:
            return attrs

        # Ownership
        if booking and booking.tenant_id != user.id:
            raise serializers.ValidationError({"booking": "Only the tenant can review this booking."})

        # Status & timing
        if booking and booking.status != Booking.CONFIRMED:
            raise serializers.ValidationError({"booking": "Only CONFIRMED bookings can be reviewed."})
        if booking and timezone.localdate() < booking.date_to:
            raise serializers.ValidationError({"booking": "You can review only after the stay has ended."})

        # Optional cross-check: if client also sent `ad`, ensure it matches booking.ad
        if booking and ad and booking.ad_id != ad.id:
            raise serializers.ValidationError({"ad": "Booking does not belong to this ad."})

        # One review per booking
        if booking and Review.objects.filter(booking=booking).exists():
            raise serializers.ValidationError({"booking": "This booking is already reviewed."})

        return attrs

    def create(self, validated_data):
        """
        Force tenant and ad to be derived from booking to keep integrity.
        """
        request = self.context["request"]
        booking = validated_data["booking"]
        validated_data["tenant"] = request.user
        validated_data["ad"] = booking.ad
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Do not allow changing the ad of an existing review — it breaks integrity.
        new_ad = validated_data.get("ad")
        if new_ad is not None and new_ad.id != instance.ad_id:
            raise serializers.ValidationError({"ad": "Cannot change ad for an existing review."})
        # Optionally forbid changing booking as well
        if "booking" in validated_data and validated_data["booking"].id != instance.booking_id:
            raise serializers.ValidationError({"booking": "Cannot change booking for an existing review."})
        # Optional: lock rating after creation (uncomment if you need it)
        # if "rating" in validated_data and validated_data["rating"] != instance.rating:
        #     raise serializers.ValidationError({"rating": "Rating cannot be edited."})
        return super().update(instance, validated_data)


class AdSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    images = AdImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_count = serializers.IntegerField(read_only=True)
    housing_type = serializers.ChoiceField(choices=Ad.HousingType.choices)

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

        if self.instance is None:
            if lat is None or lon is None:
                raise serializers.ValidationError(
                    {"detail": "Set the map pin to provide latitude and longitude."}
                )
        return attrs


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
    def validate(self, attrs):
        """
        Test expectations:
        - inactive ad -> key 'ad'
        - own ad      -> key 'non_field_errors'
        - wrong order -> key 'date_to' with phrase 'greater than date_from'
        - date_from must be tomorrow+ -> key 'date_from'
        - confirmed overlap -> key 'non_field_errors'
        """
        request = self.context["request"]
        user = request.user

        ad = attrs.get("ad") or getattr(self.instance, "ad", None)
        date_from = attrs.get("date_from") or getattr(self.instance, "date_from", None)
        date_to = attrs.get("date_to") or getattr(self.instance, "date_to", None)

        errors = {}

        # 1) Ad activity FIRST so tests see 'ad' even если даты кривые
        if ad and not getattr(ad, "is_active", True):
            errors["ad"] = ["This ad is inactive."]

        # 2) Own ad -> non_field_errors
        if ad and ad.owner_id == user.id:
            errors.setdefault("non_field_errors", []).append("You cannot book your own ad.")

        # 3) Dates — всегда формируем обе ошибки, если нужно
        if date_from is not None and date_to is not None:
            # порядок дат — тест ждёт 'greater than date_from' в ключе date_to
            if date_to <= date_from:
                errors.setdefault("date_to", []).append("must be greater than date_from")
            # date_from не ранее завтра
            today = timezone.localdate()
            if date_from <= today:
                errors.setdefault("date_from", []).append("Start date must be at least tomorrow.")
            # 4) Оверлап с CONFIRMED — только если выше базовые проверки не насыпали ошибок
            if not errors:
                overlap = Booking.objects.filter(
                    ad=ad, status=Booking.CONFIRMED,
                    date_from__lte=date_to, date_to__gte=date_from
                )
                if self.instance:
                    overlap = overlap.exclude(pk=self.instance.pk)
                if overlap.exists():
                    errors.setdefault("non_field_errors", []).append(
                        "Requested dates overlap with a confirmed booking."
                    )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def update(self, instance, validated_data):
        # Forbid changing immutable relations
        if "ad" in validated_data and validated_data["ad"].id != instance.ad_id:
            raise serializers.ValidationError({"ad": "Cannot change ad for an existing booking."})
        if "tenant" in validated_data and validated_data["tenant"].id != instance.tenant_id:
            raise serializers.ValidationError({"tenant": "Cannot change tenant for an existing booking."})
        return super().update(instance, validated_data)

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
