from django.db.models import Q, Avg
from django_filters import rest_framework as df
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import (extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample,
                                   OpenApiResponse)

from .models import Ad, Booking, AdImage
from .serializers import AdSerializer, BookingSerializer, AdImageSerializer, AdImageUploadSerializer
from .permissions import IsAdOwnerOrReadOnly, IsBookingOwnerOrAdOwner
from .pagination import AdPagination


# -------------------------
# Filters for Ads (readable labels + smart search 'q')
# -------------------------
class AdFilter(df.FilterSet):
    price_min    = df.NumberFilter(field_name='price', lookup_expr='gte', label='Price min')
    price_max    = df.NumberFilter(field_name='price', lookup_expr='lte', label='Price max')
    rooms_min    = df.NumberFilter(field_name='rooms', lookup_expr='gte', label='Rooms min')
    rooms_max    = df.NumberFilter(field_name='rooms', lookup_expr='lte', label='Rooms max')
    location     = df.CharFilter(field_name='location', lookup_expr='icontains', label='Location (contains)')
    housing_type = df.CharFilter(field_name='housing_type', lookup_expr='iexact', label='Housing type (exact)')
    area_min = df.NumberFilter(field_name='area', lookup_expr='gte', label='Area min (m²)')
    area_max = df.NumberFilter(field_name='area', lookup_expr='lte', label='Area max (m²)')

    q = df.CharFilter(method='filter_q', label='Search')
    mine = df.BooleanFilter(method='filter_mine', label='Only my ads')

    def filter_q(self, queryset, name, value):
        terms = [t.strip() for t in (value or "").split() if t.strip()]
        for term in terms:
            queryset = queryset.filter(
                Q(title__icontains=term) |
                Q(description__icontains=term) |
                Q(location__icontains=term) |
                Q(housing_type__icontains=term)
            )
        return queryset

    def filter_mine(self, queryset, name, value):
        """Return only ads owned by the current authenticated user."""
        req = getattr(self, 'request', None)
        if value and req and req.user.is_authenticated:
            return queryset.filter(owner=req.user)
        return queryset

    class Meta:
        model = Ad
        fields = ['q', 'price_min', 'price_max', 'rooms_min', 'rooms_max', 'location', 'housing_type', 'area_min',
                  'area_max', 'mine']


# -------------------------
# Ad ViewSet
# -------------------------
@extend_schema_view(
    list=extend_schema(
        summary="List ads",
        description="Public list with smart search (`q`), filters (price, rooms, location, type), ordering and pagination.",
        auth=[],
        parameters=[
            OpenApiParameter(
                name="q",
                type=OpenApiTypes.STR,
                description="Smart search in title/description/location/housing_type",
                examples=[
                    OpenApiExample("Single term", value="berlin"),
                    OpenApiExample("Multiple terms (AND)", value="berlin balcony"),
                ],
            ),
            OpenApiParameter(
                name="price_min",
                type=OpenApiTypes.NUMBER,
                description="Minimum price (>=)",
                examples=[OpenApiExample("Min 600", value=600)]
            ),
            OpenApiParameter(
                name="price_max",
                type=OpenApiTypes.NUMBER,
                description="Maximum price (<=)",
                examples=[OpenApiExample("Max 1500", value=1500)]
            ),
            OpenApiParameter(
                name="rooms_min",
                type=OpenApiTypes.INT,
                description="Minimum number of rooms (>=)",
                examples=[OpenApiExample("At least 2 rooms", value=2)]
            ),
            OpenApiParameter(
                name="rooms_max",
                type=OpenApiTypes.INT,
                description="Maximum number of rooms (<=)",
                examples=[OpenApiExample("Up to 3 rooms", value=3)]
            ),
            OpenApiParameter(
                name="location",
                type=OpenApiTypes.STR,
                description="Filter by location (icontains)",
                examples=[OpenApiExample("City contains 'ber'", value="ber")]
            ),
            OpenApiParameter(
                name="housing_type",
                type=OpenApiTypes.STR,
                description="Filter by housing type (iexact)",
                examples=[OpenApiExample("Exact type", value="apartment")]
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                description="Ordering: price, -price, created_at, -created_at",
                examples=[
                    OpenApiExample("Cheapest first", value="price"),
                    OpenApiExample("Newest first", value="-created_at"),
                ],
            ),
            OpenApiParameter(
                name="page",
                type=OpenApiTypes.INT,
                description="Page number (>=1)",
                examples=[OpenApiExample("First page", value=1)]
            ),
            OpenApiParameter(
                name="page_size",
                type=OpenApiTypes.INT,
                description="Items per page (<=50)",
                examples=[OpenApiExample("20 per page", value=20)]
            ),
            OpenApiParameter(
                name="mine",
                type=OpenApiTypes.BOOL,
                description="If true, return only ads owned by the current user",
                examples=[OpenApiExample("Only my ads", value=True)],
            ),
        ],
        examples=[
            OpenApiExample(
                "Example query (URL)",
                description="q=berlin&price_min=600&rooms_min=2&ordering=price&page=1&page_size=20",
                value=None,  # informational only (query params above)
            )
        ],
    ),
    retrieve=extend_schema(
        summary="Retrieve ad",
        description="Public details of a specific ad.",
        auth=[],
    ),
    create=extend_schema(
        summary="Create ad",
        description="Create a new ad (only for authenticated users).",
        examples=[
            OpenApiExample(
                "Ad creation example",
                value={
                    "title": "Modern apartment in Berlin",
                    "description": "Spacious 2-room apartment near Alexanderplatz",
                    "location": "Berlin",
                    "price": 1200,
                    "rooms": 2,
                    "housing_type": "apartment",
                    "is_active": True
                }
            )
        ],
        responses={
            201: OpenApiResponse(response=AdSerializer, description="Ad created"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
        }
    ),
    update=extend_schema(summary="Update ad", description="Update an ad (only for the owner)."),
    partial_update=extend_schema(summary="Partial update ad", description="Partially update an ad (only for the owner)."),
    destroy=extend_schema(summary="Delete ad", description="Delete an ad (only for the owner)."),
)
class AdViewSet(viewsets.ModelViewSet):
    queryset = Ad.objects.all()
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)
    pagination_class = AdPagination

    filter_backends = (df.DjangoFilterBackend, filters.OrderingFilter)
    filterset_class = AdFilter
    ordering_fields = ('price', 'created_at', 'area')
    ordering = ('-created_at',)

    def get_queryset(self):
        # show only active ads + avg rating
        return (
            super()
            .get_queryset()
            .filter(is_active=True)
            .annotate(average_rating=Avg('reviews__rating'))
            .select_related('owner')
            .prefetch_related('images')
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_serializer_class(self):
        """Use dedicated serializer for upload_image action"""
        if getattr(self, 'action', None) == 'upload_image':
            return AdImageUploadSerializer
        return super().get_serializer_class()

    @extend_schema(
        summary="Upload image(s) for an ad (owner only)",
        description=(
                "Send multipart/form-data.\n"
                "- `image`: single file\n"
                "- `images`: multiple files (repeat the field)\n"
                "Optional `caption` applies to all files in the request."
        ),
        request=AdImageUploadSerializer,
        responses={201: OpenApiResponse(response=AdImageSerializer(many=True), description="Created images")},
    )
    @action(detail=True, methods=["post"], url_path="images", parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        """Create one or many AdImage objects for the Ad."""
        ad = self.get_object()
        # object-level permission (IsAdOwnerOrReadOnly)
        self.check_object_permissions(request, ad)

        # validate form fields (caption, single image)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        caption = serializer.validated_data.get("caption", "")

        # accept multiple files via `images` or a single one via validated `image`
        files = request.FILES.getlist("images")
        if not files:
            single = serializer.validated_data.get("image")
            if single is not None:
                files = [single]

        if not files:
            return Response(
                {"detail": 'No files provided. Use "image" or repeated "images".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = [AdImage.objects.create(ad=ad, image=f, caption=caption) for f in files]
        return Response(AdImageSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


# -------------------------
# Booking ViewSet
# -------------------------
@extend_schema_view(
    list=extend_schema(
        summary="List my related bookings",
        description="Show bookings where you are either the tenant or the ad owner."
    ),
    retrieve=extend_schema(
        summary="Retrieve booking",
        description="Booking details visible only to tenant or ad owner."
    ),
    create=extend_schema(
        summary="Create a booking request",
        description=(
            "Authenticated users only.\n\n"
            "- Cannot book your own ad\n"
            "- Cannot book inactive ads\n"
            "- Dates must not overlap with existing confirmed/pending bookings"
        ),
        examples=[
            OpenApiExample(
                "Successful booking",
                value={"ad": 1, "date_from": "2025-09-01", "date_to": "2025-09-10"}
            ),
            OpenApiExample(
                "Overlap (will fail)",
                value={"ad": 1, "date_from": "2025-09-05", "date_to": "2025-09-07"},
                response_only=True
            ),
        ],
        responses={
            201: OpenApiResponse(response=BookingSerializer, description="Booking created"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
        }
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
        return Booking.objects.filter(
            Q(tenant=user) | Q(ad__owner=user)
        ).select_related('ad', 'tenant')

    def get_serializer_context(self):
        """Be explicit: ensure request is in serializer context."""
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        """Forbid booking own ad and set tenant."""
        ad = serializer.validated_data.get('ad')
        if ad and ad.owner_id == self.request.user.id:
            raise ValidationError({"detail": "You cannot book your own ad."})
        serializer.save(tenant=self.request.user)

    @extend_schema(
        summary="Cancel booking (tenant only)",
        responses={
            200: OpenApiResponse(description="Booking cancelled"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Cancelled'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Confirm booking (ad owner only)",
        description="Also automatically cancels overlapping pending bookings for the same ad and dates.",
        responses={
            200: OpenApiResponse(description="Booking confirmed"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        }
    )
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CONFIRMED
        booking.save(update_fields=['status'])
        # auto-cancel overlapping pending bookings
        Booking.objects.filter(
            ad=booking.ad,
            status='PENDING',
            date_from__lte=booking.date_to,
            date_to__gte=booking.date_from
        ).exclude(pk=booking.pk).update(status=Booking.CANCELLED)
        return Response({'detail': 'Confirmed'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Reject booking (ad owner only)",
        responses={
            200: OpenApiResponse(description="Booking rejected"),
            403: OpenApiResponse(description="Forbidden"),
            404: OpenApiResponse(description="Not found"),
        }
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Rejected'}, status=status.HTTP_200_OK)
