from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes
from django_filters import rest_framework as df
from django.db import models
from django.db.models import Q

from .models import Ad, Booking
from .serializers import AdSerializer, BookingSerializer
from .permissions import IsAdOwnerOrReadOnly, IsBookingOwnerOrAdOwner
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


@extend_schema_view(
    list=extend_schema(
        summary="List my related bookings",
        description="List bookings where you are the tenant or the ad owner.",
    ),
    retrieve=extend_schema(
        summary="Get a booking details",
        description="Visible only to booking tenant or ad owner.",
    ),
    create=extend_schema(
        summary="Create a booking request",
        description="Authenticated users only.",
    ),
)
class BookingViewSet(viewsets.ModelViewSet):
    """
    - list: show bookings for current user (as tenant OR as ad owner)
    - create: create booking as current user (tenant)
    - confirm/reject: only ad owner
    - cancel: only booking tenant
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = (permissions.IsAuthenticated, IsBookingOwnerOrAdOwner)

    def get_queryset(self):
        user = self.request.user
        # user as tenant OR as ad owner
        return Booking.objects.filter(
            models.Q(tenant=user) | models.Q(ad__owner=user)
        ).select_related('ad', 'tenant')

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user)

    @extend_schema(summary="Cancel my booking (tenant only)")
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Cancelled'}, status=status.HTTP_200_OK)

    @extend_schema(summary="Confirm booking (ad owner only)")
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CONFIRMED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Confirmed'}, status=status.HTTP_200_OK)

    @extend_schema(summary="Reject booking (ad owner only)")
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Rejected'}, status=status.HTTP_200_OK)
