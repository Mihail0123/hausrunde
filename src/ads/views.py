import logging
from django.db.models import Q, Avg, Count, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as df
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied, MethodNotAllowed
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework import serializers as rf_serializers
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import (
    extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import timedelta
from hashlib import blake2b

from .models import Ad, Booking, AdImage, Review, SearchQuery, AdView
from .serializers import (
    AdSerializer, BookingSerializer, AdImageSerializer, AdImageUploadSerializer,
    AvailabilityItemSerializer, ReviewSerializer, AdImageCaptionUpdateSerializer
)
from .permissions import (
    IsAdOwnerOrReadOnly, IsBookingOwnerOrAdOwner, IsReviewOwnerOrAdmin
)
from .pagination import AdPagination
from .validators import validate_image_file
from .throttling import ScopedRateThrottleIsolated


logger = logging.getLogger(__name__)

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
    area_min     = df.NumberFilter(field_name='area', lookup_expr='gte', label='Area min (m²)')
    area_max     = df.NumberFilter(field_name='area', lookup_expr='lte', label='Area max (m²)')
    lat_min = df.NumberFilter(field_name='latitude', lookup_expr='gte', label='Latitude min')
    lat_max = df.NumberFilter(field_name='latitude', lookup_expr='lte', label='Latitude max')
    lon_min = df.NumberFilter(field_name='longitude', lookup_expr='gte', label='Longitude min')
    lon_max = df.NumberFilter(field_name='longitude', lookup_expr='lte', label='Longitude max')

    q    = df.CharFilter(method='filter_q', label='Search')
    mine = df.BooleanFilter(method='filter_mine', label='Only my ads')
    rating_min = df.NumberFilter(method='filter_rating_min', label='Min average rating')
    rating_max = df.NumberFilter(method='filter_rating_max', label='Max average rating')
    available_from = df.DateFilter(method='filter_available', label='Available from (YYYY-MM-DD)')
    available_to   = df.DateFilter(method='filter_available', label='Available to (YYYY-MM-DD)')

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
        if not value:  # mine не запрошен
            return queryset

        req = getattr(self, 'request', None)
        user = getattr(req, 'user', None)

        if not user or not user.is_authenticated:
            return queryset.none()

        return queryset.filter(owner=user)

    def filter_rating_min(self, queryset, name, value):
        try:
            v = float(value)
        except (ValueError, TypeError):
            return queryset
        return queryset.filter(average_rating__gte=v)

    def filter_rating_max(self, queryset, name, value):
        try:
            v = float(value)
        except (ValueError, TypeError):
            return queryset
        return queryset.filter(average_rating__lte=v)

    def _availability_range(self):
        """
        Read both params from query and parse to dates.
        If only one is provided, treat it as a single-day window [d..d].
        """
        req = getattr(self, 'request', None)
        if not req:
            return None, None
        s = req.query_params.get('available_from') or None
        e = req.query_params.get('available_to') or None
        d1 = parse_date(s) if s else None
        d2 = parse_date(e) if e else None
        if d1 and not d2:
            d2 = d1
        if d2 and not d1:
            d1 = d2
        return d1, d2

    def filter_available(self, queryset, name, value):
        """
        Exclude ads having any CONFIRMED booking overlapping the requested window.
        Overlap condition: existing.date_from <= req_end AND existing.date_to >= req_start
        """
        # Prevent applying twice (method bound to two fields).
        if getattr(self, '_availability_applied', False):
            return queryset

        start, end = self._availability_range()
        if not start or not end:
            return queryset

        conflict = Booking.objects.filter(
            ad=OuterRef('pk'),
            status=Booking.CONFIRMED,
            date_from__lte=end,
            date_to__gte=start,
        )
        self._availability_applied = True
        return queryset.exclude(Exists(conflict))

    class Meta:
        model = Ad
        fields = [
            'q', 'price_min', 'price_max',
            'rooms_min', 'rooms_max',
            'location', 'housing_type',
            'area_min', 'area_max',
            'mine',
            'available_from', 'available_to',
            'lat_min', 'lat_max', 'lon_min', 'lon_max',
            'rating_min', 'rating_max',
        ]


# -------------------------
# Ad ViewSet
# -------------------------
@extend_schema(tags=["ads"])
@extend_schema_view(
    list=extend_schema(
        summary="List ads",
        description="Search/browse public ads with filters and ordering.",
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
                name="lat_min",
                type=OpenApiTypes.NUMBER,
                description="Minimum latitude (>=).",
                examples=[OpenApiExample("South boundary", value=52.3)],
            ),
            OpenApiParameter(
                name="lat_max",
                type=OpenApiTypes.NUMBER,
                description="Maximum latitude (<=).",
                examples=[OpenApiExample("North boundary", value=52.7)],
            ),
            OpenApiParameter(
                name="lon_min",
                type=OpenApiTypes.NUMBER,
                description="Minimum longitude (>=).",
                examples=[OpenApiExample("West boundary", value=13.2)],
            ),
            OpenApiParameter(
                name="lon_max",
                type=OpenApiTypes.NUMBER,
                description="Maximum longitude (<=).",
                examples=[OpenApiExample("East boundary", value=13.6)],
            ),
            OpenApiParameter(
                name="housing_type",
                type=OpenApiTypes.STR,
                description="Filter by housing type (iexact)",
                examples=[OpenApiExample("Exact type", value="apartment")]
            ),
            OpenApiParameter(
                name="available_from",
                type=OpenApiTypes.DATE,
                description="Exclude ads that have CONFIRMED bookings overlapping this window start.",
                examples=[OpenApiExample("From 2025-09-01", value="2025-09-01")],
            ),
            OpenApiParameter(
                name="available_to",
                type=OpenApiTypes.DATE,
                description="Exclude ads that have CONFIRMED bookings overlapping this window end.",
                examples=[OpenApiExample("To 2025-09-10", value="2025-09-10")],
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                description=(
                    "Ordering: price, -price, created_at, -created_at, "
                    "area, -area, reviews_count, -reviews_count, views_count, -views_count, "
                    "average_rating, -average_rating"
                ),
                examples=[
                    OpenApiExample("Cheapest first", value="price"),
                    OpenApiExample("Newest first", value="-created_at"),
                    OpenApiExample("Most reviewed first", value="-reviews_count"),
                    OpenApiExample("Most viewed first", value="-views_count"),
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
                value=None,
            ),
            OpenApiExample(
                "Filter by availability window",
                description="q=berlin&available_from=2025-09-01&available_to=2025-09-10&page=1&page_size=20",
                value=None,
            ),

        ],
    ),
    create=extend_schema(
        summary="Create ad",
        description=(
                "Create a new ad (only for authenticated users).\n"
                "Latitude/Longitude are set by the MAP PIN in the UI; "
                "in Swagger you can type them manually for testing."
        ),
        examples=[
            OpenApiExample(
                "Ad creation with map coordinates",
                value={
                    "title": "Cozy studio in Kreuzberg",
                    "description": "Bright, quiet, close to U-Bahn.",
                    "location": "Berlin, Kreuzberg",
                    "price": 85,
                    "rooms": 1,
                    "area": 28,
                    "housing_type": "apartment",
                    "latitude": 52.500312,
                    "longitude": 13.423901
                },
                request_only=True,
            )
        ],
        responses={
            201: OpenApiResponse(response=AdSerializer, description="Ad created"),
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Unauthorized"),
        }
    ),
    retrieve=extend_schema(
        summary="Retrieve ad",
        description="Get a single ad with aggregates (rating, reviews_count, views_count).",
        auth=[],
        responses={200: OpenApiResponse(response=AdSerializer, description="Ad")}
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
    ordering_fields = ('price', 'created_at', 'area', 'reviews_count', 'views_count', 'average_rating')
    ordering = ('-created_at',)

    # Per-action throttling
    throttle_classes = (ScopedRateThrottleIsolated,)

    def get_throttles(self):
        scope_map = {
            'list': 'ads_list',
            'retrieve': 'ads_retrieve',
            'availability': 'ads_availability',
            'upload_image': 'adimage_upload',
        }
        self.throttle_scope = scope_map.get(getattr(self, 'action', None))
        return super().get_throttles()

    def get_queryset(self):
        """
        Base queryset with aggregates. Public users see only active ads.
        When ?mine=true and user is authenticated, include owner's inactive ads as well.
        """
        qs = (
            Ad.objects.all()
            .annotate(
                average_rating=Avg('reviews__rating'),
                reviews_count=Count('reviews', distinct=True),
                views_count=Count('views', distinct=True),
            )
            .select_related('owner')
            .prefetch_related('images')
        )

        # Detect ?mine=true (truthy variants: 1,true,yes,on)
        try:
            mine_param = self.request.query_params.get('mine', '')
            mine = str(mine_param).lower() in {'1', 'true', 'yes', 'on'}
        except Exception:
            mine = False

        # For everyone except the owner-view (?mine=true), restrict to active ads
        if not (mine and self.request.user.is_authenticated):
            qs = qs.filter(is_active=True)

        return qs

    # --- search logging (list) ---
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        try:
            params = request.query_params  # QueryDict
            q = (params.get('q') or '').strip()
            if q:
                filters_payload = dict(params.lists())
                filters_payload.pop('page', None)
                filters_payload.pop('page_size', None)
                xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
                ip = xff or request.META.get('REMOTE_ADDR') or None
                data = {
                    "q": q,
                    "filters": filters_payload,
                    "user": request.user if request.user.is_authenticated else None,
                    "ip": ip,
                    "user_agent": request.META.get("HTTP_USER_AGENT") or "",
                }
                SearchQuery.objects.create(**data)
        except Exception as e:
            logger.warning("search logging failed: %s", e)
        return response

    # --- view logging (retrieve) ---
    @staticmethod
    def _first_ip_from_xff(xff_header: str) -> str:
        if not xff_header:
            return ''
        return xff_header.split(',')[0].strip()

    @staticmethod
    def _hash_ip(ip: str) -> str:
        if not ip:
            return ''
        h = blake2b(digest_size=20)  # 160-bit is compact and sufficient
        h.update(f"{ip}|{getattr(settings, 'ADS_ANON_IP_SALT', settings.SECRET_KEY)}".encode('utf-8'))
        return h.hexdigest()

    def retrieve(self, request, *args, **kwargs):
        """
        Detail view with immediate views_count update on the first GET.
        Authenticated: dedup by user within ADS_VIEW_DEDUP_HOURS (no IP stored).
        Anonymous: dedup by salted hashed IP within ADS_VIEW_DEDUP_HOURS (raw IP not stored).
        """
        # 1) fetch the object (with annotations)
        obj = self.get_object()

        # 2) log the view (best-effort; never break the response)
        try:
            hours = int(getattr(settings, 'ADS_VIEW_DEDUP_HOURS', 6))
            cutoff = timezone.now() - timedelta(hours=hours)
            ua = (request.META.get('HTTP_USER_AGENT') or '')[:1000]

            if request.user.is_authenticated:
                exists = AdView.objects.filter(ad=obj, user=request.user, created_at__gte=cutoff).exists()
                if not exists:
                    AdView.objects.create(ad=obj, user=request.user, ip=None, anon_ip_hash=None, user_agent=ua)
            else:
                xff = self._first_ip_from_xff(request.META.get('HTTP_X_FORWARDED_FOR', ''))
                ip = xff or (request.META.get('REMOTE_ADDR') or '')
                ip_hash = self._hash_ip(ip) if ip else ''

                if ip_hash:
                    exists = (
                        AdView.objects
                        .filter(ad=obj, user__isnull=True, created_at__gte=cutoff)
                        # consider legacy rows with raw IP to avoid double-count after deploy
                        .filter(Q(anon_ip_hash=ip_hash) | Q(ip=ip))
                        .exists()
                    )
                    if not exists:
                        AdView.objects.create(ad=obj, user=None, anon_ip_hash=ip_hash, ip=None, user_agent=ua)
        except Exception:
            pass

        # 3) re-fetch the object so annotated views_count includes the freshly created row
        obj = self.get_queryset().get(pk=obj.pk)

        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    def get_serializer_class(self):
        """Use dedicated serializer for upload_image action."""
        if getattr(self, 'action', None) == 'upload_image':
            return AdImageUploadSerializer
        return super().get_serializer_class()

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        """Bind owner to the authenticated user on create."""
        serializer.save(owner=self.request.user)

    @extend_schema(
        summary="Upload image(s) for an ad (owner only)",
        description=(
                "Send multipart/form-data.\n"
                "- `image`: single file\n"
                "- `images`: multiple files (repeat the field)\n"
                "Optional `caption` applies to all files in the request."
        ),
        request=AdImageUploadSerializer,
        responses={
            201: OpenApiResponse(response=AdImageSerializer(many=True), description="Created images"),
            400: OpenApiResponse(description="Invalid image or limit exceeded"),
        },
    )
    @action(detail=True, methods=["post"], url_path="images", parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        """Create one or many AdImage objects for the Ad."""
        ad = self.get_object()
        # object-level permission (IsAdOwnerOrReadOnly)
        self.check_object_permissions(request, ad)

        # validate known fields only (caption + optional single "image")
        payload = {"caption": request.data.get("caption", "")}
        if "image" in request.FILES:
            payload["image"] = request.FILES["image"]
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        caption = serializer.validated_data.get("caption", request.data.get("caption", ""))

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

        # enforce per-ad image limit BEFORE creating anything
        existing = ad.images.count()
        incoming = len(files)
        max_total = int(getattr(settings, "AD_IMAGES_MAX_PER_AD", 20))
        if existing + incoming > max_total:
            return Response(
                {
                    "detail": f"Too many images. Limit {max_total} per ad. "
                              f"You already have {existing}, tried to add {incoming}."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # validate each file (size/format/dimensions)
        errors = []
        valid_files = []
        for idx, f in enumerate(files, start=1):
            try:
                validate_image_file(f)
                valid_files.append(f)
            except DjangoValidationError as e:
                errors.append({"file_index": idx, "error": str(e)})

        if errors:
            return Response({"detail": "Invalid images", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        created = [AdImage.objects.create(ad=ad, image=f, caption=caption) for f in valid_files]
        return Response(AdImageSerializer(created, many=True, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


    @extend_schema(
        summary="Ad availability (busy intervals)",
        description="Returns date ranges blocked by PENDING or CONFIRMED bookings.",
        auth=[],
        responses={200: OpenApiResponse(response=AvailabilityItemSerializer(many=True))},
        parameters=[
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                description="Optional: limit to single status. One of: PENDING, CONFIRMED.",
                examples=[OpenApiExample("Only confirmed", value="CONFIRMED")]
            ),
        ],
    )
    @action(detail=True, methods=['get'], url_path='availability', permission_classes=[permissions.AllowAny])
    def availability(self, request, pk=None):
        """Return busy intervals for calendar (PENDING and/or CONFIRMED)."""
        ad = self.get_object()

        # base queryset: busy bookings
        qs = ad.bookings.filter(status__in=[Booking.PENDING, Booking.CONFIRMED])

        # optional filter by status
        status_param = (request.query_params.get('status') or '').upper().strip()
        if status_param in (Booking.PENDING, Booking.CONFIRMED):
            qs = qs.filter(status=status_param)

        qs = qs.order_by('date_from').values('date_from', 'date_to', 'status')
        data = AvailabilityItemSerializer(qs, many=True).data
        return Response(data, status=status.HTTP_200_OK)


# -------------------------
# Review ViewSet
# -------------------------
@extend_schema(tags=["reviews"])
@extend_schema_view(
    list=extend_schema(
        summary="List reviews",
        parameters=[
            OpenApiParameter(name="ad", type=OpenApiTypes.INT,
                             description="Filter by ad id",
                             examples=[OpenApiExample("For ad #1", value=1)]),
            OpenApiParameter(name="ordering", type=OpenApiTypes.STR,
                             description="Ordering: -created_at, created_at, -rating, rating"),
        ],
        auth=[],
    ),
    retrieve=extend_schema(summary="Retrieve review", auth=[]),
    create=extend_schema(
        summary="Create review (only after finished CONFIRMED booking)",
        responses={201: OpenApiResponse(response=ReviewSerializer)},
    ),
    update=extend_schema(summary="Update review (author or staff)"),
    partial_update=extend_schema(summary="Partial update review (author or staff)"),
    destroy=extend_schema(summary="Delete review (author or staff)"),
)
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related('ad', 'tenant').all()
    serializer_class = ReviewSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrAdmin)
    filter_backends = (df.DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ('ad',)
    ordering_fields = ('created_at', 'rating')
    ordering = ('-created_at',)

    def get_permissions(self):
        if self.action in ('create',):
            return (permissions.IsAuthenticated(),)
        return super().get_permissions()

    def perform_create(self, serializer):
        """
        Allow two flows for backward compatibility with tests:
        1) Client sends `booking`: we validate and use it.
        2) Client sends only `ad`: bind to the latest finished CONFIRMED booking
           of the current user for that ad that has no review yet.
        """
        user = self.request.user
        today = timezone.localdate()

        booking = serializer.validated_data.get("booking")
        if not booking:
            # fallback by ad (tests post only `ad`)
            ad_id = self.request.data.get("ad") or serializer.validated_data.get("ad")
            if not ad_id:
                raise ValidationError({"detail": "Provide 'ad' or 'booking'."})
            ad = get_object_or_404(Ad, pk=ad_id) if not hasattr(ad_id, "id") else ad_id
            booking = (
                Booking.objects
                .filter(ad=ad, tenant=user, status=Booking.CONFIRMED, date_to__lt=today, review__isnull=True)
                .order_by("-date_to")
                .first()
            )
            if not booking:
                raise ValidationError({"detail": "You can review only after a finished CONFIRMED booking for this ad."})
        else:
            ad = booking.ad

        # ownership/status/timing
        if booking.tenant_id != user.id:
            raise ValidationError({"detail": "Only the tenant can review this booking."})
        if booking.status != Booking.CONFIRMED:
            raise ValidationError({"detail": "Only CONFIRMED bookings can be reviewed."})
        if booking.date_to >= today:
            raise ValidationError({"detail": "You can review only after the stay has ended."})
        if Review.objects.filter(booking=booking).exists():
            raise ValidationError({"detail": "This booking is already reviewed."})

        serializer.save(tenant=user, ad=ad, booking=booking)


# -------------------------
# AdImage ViewSet (edit/delete single image)
# -------------------------
@extend_schema(tags=["ads"])
@extend_schema_view(
    list=extend_schema(
        summary="List ad images",
        parameters=[
            OpenApiParameter(name="ad", type=OpenApiTypes.INT,
                             description="Filter by ad id",
                             examples=[OpenApiExample("For ad #1", value=1)]),
        ],
        auth=[],
    ),
    partial_update=extend_schema(
        summary="Update image caption (ad owner only)",
        examples=[OpenApiExample("Set caption", value={"caption": "Kitchen view"})],
    ),
    destroy=extend_schema(
        summary="Delete image (ad owner only)",
    ),
)
class AdImageViewSet(viewsets.ModelViewSet):
    """
    POST/CREATE disabled: upload happens via /api/ads/{id}/images/.
    This ViewSet supports:
      - GET    /api/ad-images/?ad=ID
      - PATCH  /api/ad-images/{id}/     {"caption": "..."}  (owner only)
      - DELETE /api/ad-images/{id}/                         (owner only)
    """
    queryset = AdImage.objects.select_related('ad').all()
    serializer_class = AdImageSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly,)
    http_method_names = ['get', 'patch', 'delete', 'post', 'head', 'options']
    filter_backends = (df.DjangoFilterBackend,)
    filterset_fields = ('ad',)

    # Per-action throttling
    throttle_classes = (ScopedRateThrottle,)

    def get_throttles(self):
        scope_map = {
            'replace': 'adimage_replace',
        }
        self.throttle_scope = scope_map.get(getattr(self, 'action', None))
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        # Disallow POST /api/ad-images/ (file upload happens via /api/ads/{id}/images/ and /ad-images/{id}/replace/)
        raise MethodNotAllowed('POST')

    def get_serializer_class(self):
        # Use caption-only serializer for PATCH to avoid replacing the file
        if self.action == "partial_update":
            return AdImageCaptionUpdateSerializer
        return super().get_serializer_class()

    def _is_owner(self, obj):
        u = self.request.user
        return bool(u and u.is_authenticated and (u.is_staff or getattr(obj.ad, "owner_id", None) == u.id))

    def perform_update(self, serializer):
        obj = self.get_object()
        if not self._is_owner(obj):
            raise PermissionDenied("Only the ad owner can update image metadata.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._is_owner(instance):
            raise PermissionDenied("Only the ad owner can delete images.")
        instance.delete()

    @extend_schema(
        summary="Replace image file (owner only)",
        description="Multipart: field `image` (required), optional `caption` to update together with file.",
        request=None,
        responses={
            200: OpenApiResponse(response=AdImageSerializer),
            400: OpenApiResponse(description="Invalid image or missing file"),
        },
    )
    @action(detail=True, methods=['post'], url_path='replace', parser_classes=[MultiPartParser])
    def replace(self, request, pk=None):
        """
        Replace image file for an existing AdImage. Owner-only.
        Expects multipart with field 'image'; optional 'caption'.
        """
        obj = self.get_object()
        if not self._is_owner(obj):
            raise PermissionDenied("Only the ad owner can replace images.")

        file = request.FILES.get('image')
        if not file:
            return Response({"detail": "Provide file in 'image' field (multipart)."},
                            status=status.HTTP_400_BAD_REQUEST)

        # validate new file before saving
        try:
            validate_image_file(file)
        except DjangoValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        # save
        obj.image = file

        # optional caption update
        caption = request.data.get('caption')
        if caption is not None:
            obj.caption = caption

        obj.save(update_fields=['image', 'caption'] if caption is not None else ['image'])

        # return fresh representation (with image_url/path computed)
        return Response(AdImageSerializer(obj, context={'request': request}).data, status=status.HTTP_200_OK)


# -------------------------
# Booking ViewSet
# -------------------------
# Helper: cancellation quote calculator (module-level, no indent)
def _compute_cancel_quote(booking):
    """
    Policy:
      - Free: if start is in >= 4 full days.
      - 3 / 2 / 1 days before start: 20% / 40% / 60%.
      - On/after start date: 100%.

    Total cost = ad.price (per day) * nights.
    """
    today = timezone.now().date()
    days_until = (booking.date_from - today).days  # can be negative
    FREE_CUTOFF = 4  # free if >= 4 full days before start

    if days_until >= FREE_CUTOFF:
        fee_pct = 0.0
        msg = "Free cancellation is available up to 4 full days before the start date."
    elif days_until >= 1:
        # 3 -> 20%, 2 -> 40%, 1 -> 60%
        fee_pct = 0.2 * (FREE_CUTOFF - days_until)
        msg = (
            "Free cancellation is only up to 4 full days before start; "
            "inside the 3-day window the fee is 20%/40%/60% per day."
        )
    else:
        # day-of (0) or after (<0): 100%
        fee_pct = 1.0
        msg = "Start date has been reached or passed; cancellation fee is 100%."

    daily_price = float(getattr(booking.ad, "price", 0) or 0)
    nights = max(1, (booking.date_to - booking.date_from).days)
    total_cost = daily_price * nights
    fee_amount = round(total_cost * fee_pct, 2)

    return {
        "days_until_start": days_until,
        "free_cancellation_cutoff_days": FREE_CUTOFF,
        "fee_percent": round(fee_pct * 100, 2),
        "fee_amount": fee_amount,
        "currency": "EUR",
        "nights": nights,
        "total_cost": round(total_cost, 2),
        "after_start": days_until <= 0,
        "message": msg + f" Your cancellation fee would be €{fee_amount} ({round(fee_pct*100,2)}%).",
    }

@extend_schema(tags=["bookings"])
@extend_schema_view(
    list=extend_schema(
        summary="List my bookings (as tenant or ad owner)",
        description=(
                "Returns bookings where you are either the tenant or the ad owner.\n\n"
                "**Filters:**\n"
                "- `role=owner|tenant` — limit to your owner/tenant side\n"
                "- `incoming=true` — only PENDING bookings where you are the owner (inbox)\n"
                "- `status=` — DjangoFilter (e.g. PENDING, CONFIRMED, ...)\n"
                "- `ad=` — filter by ad id\n"
                "- `ordering=` — created_at, date_from, date_to, status (default -created_at)"
        ),
        parameters=[
            OpenApiParameter("role", OpenApiTypes.STR, description="owner | tenant"),
            OpenApiParameter("incoming", OpenApiTypes.BOOL, description="Only owner's PENDING bookings (inbox)"),
            OpenApiParameter("status", OpenApiTypes.STR, description="Status filter (DjangoFilter)"),
            OpenApiParameter("ad", OpenApiTypes.INT, description="Filter by ad id"),
            OpenApiParameter("ordering", OpenApiTypes.STR,
                             description="created_at | date_from | date_to | status, prefix with - for desc"),
        ],
    ),
    retrieve=extend_schema(summary="Retrieve booking"),
    create=extend_schema(
        summary="Create booking",
        examples=[
            OpenApiExample(
                "Create booking",
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
    filter_backends = (df.DjangoFilterBackend, filters.OrderingFilter)
    filterset_fields = ("status", "ad")  # ?status=PENDING&ad=123
    ordering_fields = ("created_at", "date_from", "date_to", "status")
    ordering = ("-created_at",)
    http_method_names = ['get', 'post', 'head', 'options']

    # Per-action throttling
    throttle_classes = (ScopedRateThrottle,)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_throttles(self):
        scope_map = {
            'create': 'bookings_mutation',
            'confirm': 'bookings_mutation',
            'reject': 'bookings_mutation',
            'cancel': 'bookings_mutation',
        }
        self.throttle_scope = scope_map.get(getattr(self, 'action', None))
        return super().get_throttles()

    def get_queryset(self):
        """
        Show bookings where the current user is either a tenant or the ad owner.
        Optional filters:
        - role=tenant|owner — limit to one side
        - incoming=true     — owner's inbox: only PENDING bookings for the owner's ads
        """
        user = self.request.user
        qs = (
            Booking.objects
            .filter(Q(tenant=user) | Q(ad__owner=user))
            .select_related("ad", "ad__owner", "tenant")
        )

        role = (self.request.query_params.get("role") or "").lower()
        if role == "owner":
            qs = qs.filter(ad__owner=user)
        elif role == "tenant":
            qs = qs.filter(tenant=user)

        incoming = (self.request.query_params.get("incoming") or "").lower()
        if incoming in ("1", "true", "yes"):
            qs = qs.filter(ad__owner=user, status=Booking.PENDING)

        return qs

    def get_serializer_context(self):
        """Ensure request is in serializer context."""
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        """Bind tenant to the authenticated user on create."""
        serializer.save(tenant=self.request.user)

    @extend_schema(
        summary="Preview cancellation fee (tenant only)",
        description=(
                "Tenant only. Allowed statuses: **PENDING** (always 0%) and **CONFIRMED**.\n\n"
                "Fee policy for CONFIRMED:\n"
                "- ≥ 4 full days before start: **0%**\n"
                "- 3 / 2 / 1 day(s) before start: **20% / 40% / 60%**\n"
                "- On/after start date: **100%**\n\n"
                "Returns the computed percent and amounts. Does **not** change booking status.\n\n"
                "Cancellation (`POST /cancel/`) is allowed only **before** the start date."
        ),
        responses={
            200: OpenApiResponse(description="JSON with fee percent/amount"),
            400: OpenApiResponse(description="Invalid status (not PENDING/CONFIRMED)"),
            403: OpenApiResponse(description="Forbidden (not the booking tenant)"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(detail=True, methods=['get'], url_path='cancel-quote')
    def cancel_quote(self, request, pk=None):
        booking = self.get_object()

        # Only the tenant can preview/cancel this booking
        if booking.tenant_id != request.user.id:
            raise PermissionDenied("Only the booking tenant can preview/cancel this booking.")

        if booking.status not in (Booking.PENDING, Booking.CONFIRMED):
            return Response(
                {'detail': f'Cannot cancel booking with status {booking.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        quote = _compute_cancel_quote(booking)
        if booking.status == Booking.PENDING:
            quote.update({
                "fee_percent": 0.0,
                "fee_amount": 0.0,
                "message": "No cancellation fee for PENDING bookings.",
            })
        return Response(quote, status=200)

    @extend_schema(
        summary="Cancel booking (tenant only)",
        description=(
                "Tenant only. Allowed statuses to cancel: **PENDING** and **CONFIRMED**.\n"
                "- PENDING → no fee (0%).\n"
                "- CONFIRMED → fee per policy (0 / 20 / 40 / 60 / 100%).\n\n"
                "**Time rule:** cancellation is allowed only **before** the start date (`date_from`). "
                "On/after the start date the API returns 400 and does not cancel.\n\n"
                "On success sets status to **CANCELLED** and returns the computed `cancel_quote`."
        ),
        responses={
            200: OpenApiResponse(description="Cancelled; JSON includes `cancel_quote`"),
            400: OpenApiResponse(
                description="Invalid status (neither PENDING nor CONFIRMED), already cancelled, or on/after start date"),
            403: OpenApiResponse(description="Forbidden (not the booking tenant)"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()

        # Only the tenant can cancel
        if booking.tenant_id != request.user.id:
            raise PermissionDenied("Only the booking tenant can cancel this booking.")

        # Already cancelled
        if booking.status == Booking.CANCELLED:
            return Response({'detail': 'Already cancelled'}, status=status.HTTP_400_BAD_REQUEST)

        # Allowed statuses
        if booking.status not in (Booking.PENDING, Booking.CONFIRMED):
            return Response(
                {'detail': f'Cannot cancel booking with status {booking.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Time rule: only before start date
        today = timezone.localdate()
        if today >= booking.date_from:
            return Response(
                {'detail': 'Cancellation is no longer allowed on/after the start date.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compute the quote (for UI/logging)
        quote = _compute_cancel_quote(booking)
        if booking.status == Booking.PENDING:
            quote.update({
                "fee_percent": 0.0,
                "fee_amount": 0.0,
                "message": "No cancellation fee for PENDING bookings.",
            })

        # Apply cancellation
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])

        return Response({'detail': 'Cancelled', 'cancel_quote': quote}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Confirm booking (ad owner only)",
        description=(
                "Ad owner only. Allowed to confirm **only** from status **PENDING**.\n"
                "On confirm, all overlapping **PENDING** bookings for the same ad and dates are automatically set to **CANCELLED**."
        ),
        responses={
            200: OpenApiResponse(description="Booking confirmed"),
            400: OpenApiResponse(description="Invalid current status (not PENDING)"),
            403: OpenApiResponse(description="Forbidden (not the ad owner)"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.ad.owner_id != request.user.id:
            raise PermissionDenied("Only the ad owner can confirm this booking.")
        if booking.status != Booking.PENDING:
            return Response(
                {'detail': f'Only PENDING bookings can be confirmed (current: {booking.status}).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        booking.status = Booking.CONFIRMED
        booking.save(update_fields=['status'])
        Booking.objects.filter(
            ad=booking.ad,
            status=Booking.PENDING,
            date_from__lte=booking.date_to,
            date_to__gte=booking.date_from,
        ).exclude(pk=booking.pk).update(status=Booking.CANCELLED)
        return Response({'detail': 'Confirmed'}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Reject booking (ad owner only)",
        description=(
                "Ad owner only. Allowed to reject **only** from status **PENDING**.\n"
                "Sets status to **CANCELLED**."
        ),
        responses={
            200: OpenApiResponse(description="Booking rejected"),
            400: OpenApiResponse(description="Invalid current status (not PENDING)"),
            403: OpenApiResponse(description="Forbidden (not the ad owner)"),
            404: OpenApiResponse(description="Not found"),
        },
    )
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        booking = self.get_object()
        if booking.ad.owner_id != request.user.id:
            raise PermissionDenied("Only the ad owner can reject this booking.")
        if booking.status != Booking.PENDING:
            return Response(
                {'detail': f'Only PENDING bookings can be rejected (current: {booking.status}).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])
        return Response({'detail': 'Rejected'}, status=status.HTTP_200_OK)


# -------------------------
# Top search keywords
# -------------------------

class SearchTopItemSerializer(rf_serializers.Serializer):
    q = rf_serializers.CharField()
    count = rf_serializers.IntegerField()


@extend_schema(
    summary="Top search keywords",
    description="Return most frequent non-empty `q` values.",
    parameters=[
        OpenApiParameter(
            name="limit",
            type=OpenApiTypes.INT,
            description="Max items (default 10, max 50)",
            required=False,
            examples=[OpenApiExample("Top 5", value=5)],
        )
    ],
    responses={200: OpenApiResponse(response=SearchTopItemSerializer(many=True))},
    auth=[],
    tags=["search"],
)
class SearchHistoryTopView(APIView):
    permission_classes = [permissions.AllowAny]
    renderer_classes = [JSONRenderer]
    throttle_classes = (ScopedRateThrottleIsolated,)
    throttle_scope = 'search_top'

    def get(self, request):
        limit = int(request.query_params.get('limit', 10) or 10)
        limit = max(1, min(limit, 50))
        qs = (
            SearchQuery.objects
            .exclude(q='')
            .values('q')
            .annotate(count=Count('id'))
            .order_by('-count', 'q')[:limit]
        )
        data = list(qs)
        return JsonResponse(data, safe=False, status=200)
