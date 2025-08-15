from rest_framework import viewsets, permissions, filters
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes
from django_filters import rest_framework as df
from django.db.models import Q

from .models import Ad
from .serializers import AdSerializer
from .permissions import IsAdOwnerOrReadOnly
from .pagination import AdPagination


class AdFilter(df.FilterSet):
    price_min = df.NumberFilter(field_name='price', lookup_expr='gte', label='Price min')
    price_max = df.NumberFilter(field_name='price', lookup_expr='lte', label='Price max')
    rooms_min = df.NumberFilter(field_name='rooms', lookup_expr='gte', label='Rooms min')
    rooms_max = df.NumberFilter(field_name='rooms', lookup_expr='lte', label='Rooms max')
    location = df.CharFilter(field_name='location', lookup_expr='icontains', label='Location (contains)')
    housing_type = df.CharFilter(field_name='housing_type', lookup_expr='iexact', label='Housing type (exact)')

    # smart search across multiple fields and between words
    q = df.CharFilter(method='filter_q', label='Search')

    def filter_q(self, queryset, name, value):
        terms = [t.strip() for t in value.split() if t.strip()]
        for term in terms:
            queryset = queryset.filter(
                Q(title__icontains=term) |
                Q(description__icontains=term) |
                Q(location__icontains=term) |
                Q(housing_type__icontains=term)
            )
        return queryset

    class Meta:
        model = Ad
        fields = ['q', 'price_min', 'price_max', 'rooms_min', 'rooms_max', 'location', 'housing_type']


@extend_schema_view(
    list=extend_schema(
        summary="List ads",
        description="Public list with smart search (q), filters, and ordering.",
        auth=[],
        parameters=[
            OpenApiParameter(name="q", description="Smart search in title/description/location/housing_type",
                             required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name="price_min", description="Minimum price (>=)", required=False,
                             type=OpenApiTypes.NUMBER),
            OpenApiParameter(name="price_max", description="Maximum price (<=)", required=False,
                             type=OpenApiTypes.NUMBER),
            OpenApiParameter(name="rooms_min", description="Minimum number of rooms (>=)", required=False,
                             type=OpenApiTypes.INT),
            OpenApiParameter(name="rooms_max", description="Maximum number of rooms (<=)", required=False,
                             type=OpenApiTypes.INT),
            OpenApiParameter(name="location", description="Filter by location (icontains)", required=False,
                             type=OpenApiTypes.STR),
            OpenApiParameter(name="housing_type", description="Filter by housing type (iexact)", required=False,
                             type=OpenApiTypes.STR),
            OpenApiParameter(name="ordering", description="Ordering: price, -price, created_at, -created_at",
                             required=False, type=OpenApiTypes.STR),
            OpenApiParameter(name="page", description="Page number (>=1)", required=False, type=OpenApiTypes.INT),
            OpenApiParameter(name="page_size", description="Items per page (<=50)", required=False, type=OpenApiTypes.INT),
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve ad",
        description="Public details of an ad.",
        auth=[],
    ),
    create=extend_schema(
        summary="Create ad",
        description="Create a new ad (only for authenticated users)."
    ),
    update=extend_schema(
        summary="Update ad",
        description="Update an ad (only for the owner)."
    ),
    partial_update=extend_schema(
        summary="Partial update ad",
        description="Partially update an ad (only for the owner)."
    ),
    destroy=extend_schema(
        summary="Delete ad",
        description="Delete an ad (only for the owner)."
    ),
)


class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)
    pagination_class = AdPagination

    filter_backends = (df.DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = AdFilter
    ordering_fields = ('price', 'created_at')
    ordering = ('-created_at',)

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
