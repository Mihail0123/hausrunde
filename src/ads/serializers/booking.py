from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes
from django.utils import timezone

from src.ads.models import Booking
from src.ads.serializers.common import PublicUserTinySerializer


class BookingSerializer(serializers.ModelSerializer):
    # Writable input: `ad`, `date_from`, `date_to`
    # Date fields with friendly error messages
    date_from = serializers.DateField(
        error_messages={
            "invalid": "Invalid date or format. Expected YYYY-MM-DD and a real calendar date."
        }
    )
    date_to = serializers.DateField(
        error_messages={
            "invalid": "Invalid date or format. Expected YYYY-MM-DD and a real calendar date."
        }
    )
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

        if ad and not getattr(ad, "is_active", True):
            errors["ad"] = ["This ad is inactive."]

        if ad and ad.owner_id == user.id:
            errors.setdefault("non_field_errors", []).append("You cannot book your own ad.")

        if date_from is not None and date_to is not None:
            if date_to <= date_from:
                errors.setdefault("date_to", []).append("must be greater than date_from")
            today = timezone.localdate()
            if date_from <= today:
                errors.setdefault("date_from", []).append("Start date must be at least tomorrow.")
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
        if "ad" in validated_data and validated_data["ad"].id != instance.ad_id:
            raise serializers.ValidationError({"ad": "Cannot change ad for an existing booking."})
        if "tenant" in validated_data and validated_data["tenant"].id != instance.tenant_id:
            raise serializers.ValidationError({"tenant": "Cannot change tenant for an existing booking."})
        return super().update(instance, validated_data)

    # -------------------------
    # Presentation helpers
    # -------------------------
    @extend_schema_field(PublicUserTinySerializer)
    def get_tenant(self, obj):
        t = getattr(obj, "tenant", None)
        if not t:
            return None
        return {"id": t.id, "email": t.email}

    @extend_schema_field(PublicUserTinySerializer)
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
    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_cancel(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        today = timezone.localdate()
        return (
                self._is_tenant(obj, user)
                and obj.status in (Booking.PENDING, Booking.CONFIRMED)
                and obj.date_from > today  # only before start date
        )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_cancel_quote(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        today = timezone.localdate()
        return (
                self._is_tenant(obj, user)
                and obj.status in (Booking.PENDING, Booking.CONFIRMED)
                and obj.date_from > today  # only before the start date
        )

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_confirm(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        return self._is_owner(obj, user) and obj.status == Booking.PENDING

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_reject(self, obj):
        user = getattr(self.context.get("request"), "user", None)
        return self._is_owner(obj, user) and obj.status == Booking.PENDING

