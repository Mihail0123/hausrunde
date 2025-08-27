from rest_framework import serializers


class PublicUserTinySerializer(serializers.Serializer):
    """Public projection for nested user references."""
    id = serializers.IntegerField()
    email = serializers.EmailField(allow_null=True, required=False)


class ReviewShortSerializer(serializers.Serializer):
    """Public projection for recent reviews shown on Ad cards/details."""
    id = serializers.IntegerField()
    rating = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    tenant = PublicUserTinySerializer()
    created_at = serializers.DateTimeField()