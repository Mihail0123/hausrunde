from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, OpenApiTypes

from src.ads.models import AdImage

class AdImageSerializer(serializers.ModelSerializer):
    # Absolute URL (with scheme/host) if request is in context
    image_url = serializers.SerializerMethodField()
    # Relative /media/... path
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
