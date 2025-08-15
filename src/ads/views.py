from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema_view, extend_schema

from .models import Ad
from .serializers import AdSerializer
from .permissions import IsAdOwnerOrReadOnly

class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema_view(
    list=extend_schema(
        summary="List ads",
        description="Public ad list(without authentication).",
        auth=[],
    ),
    retrieve=extend_schema(
        summary="Retrieve ad",
        description="Public ad details(without authentication).",
        auth=[],
    ),
    create=extend_schema(
        summary="Create ad",
        description="Create ad(only authenticated)."
    ),
    update=extend_schema(
        summary="Update ad",
        description="Update ad(only owner)."
    ),
    partial_update=extend_schema(
        summary="Partial update ad",
        description="Partial update ad(only owner)."
    ),
    destroy=extend_schema(
        summary="Delete ad",
        description="Delete ad(only owner)."
    ),
)
class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
