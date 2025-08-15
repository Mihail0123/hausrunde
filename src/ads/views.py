from rest_framework import viewsets, permissions

from .models import Ad
from .serializers import AdSerializer
from .permissions import IsAdOwnerOrReadOnly

class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)