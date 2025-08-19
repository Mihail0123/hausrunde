from django.db.models import Q, Avg, Count, Exists, OuterRef
from django_filters import rest_framework as df
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied, MethodNotAllowed
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

VIEW_DEDUP_HOURS = 6


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
        req = getattr(self, 'request', None)
        if value and req and req.user.is_authenticated:
            return queryset.filter(owner=req.user)
        return queryset

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
        Exclude ads having any PENDING/CONFIRMED booking overlapping the requested window.
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
            status__in=[Booking.PENDING, Booking.CONFIRMED],
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
        ]


# -------------------------
# Ad ViewSet
# -------------------------
@extend_schema(tags=["ads"])
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
                description="Exclude ads that have PENDING/CONFIRMED bookings overlapping this window start.",
                examples=[OpenApiExample("From 2025-09-01", value="2025-09-01")],
            ),
            OpenApiParameter(
                name="available_to",
                type=OpenApiTypes.DATE,
                description="Exclude ads that have PENDING/CONFIRMED bookings overlapping this window end.",
                examples=[OpenApiExample("To 2025-09-10", value="2025-09-10")],
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                description=(
                    "Ordering: price, -price, created_at, -created_at, "
                    "area, -area, reviews_count, -reviews_count, views_count, -views_count"
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
    ordering_fields = ('price', 'created_at', 'area', 'reviews_count', 'views_count')
    ordering = ('-created_at',)

    # Per-action throttling
    throttle_classes = (ScopedRateThrottle,)

    def get_throttles(self):
        # Map actions to throttle scopes
        action = getattr(self, 'action', None)
        if action == 'list':
            self.throttle_scope = 'ads_list'
        elif action == 'retrieve':
            self.throttle_scope = 'ads_retrieve'
        elif action == 'availability':
            self.throttle_scope = 'ads_availability'
        elif action == 'upload_image':
            self.throttle_scope = 'adimage_upload'
        else:
            self.throttle_scope = None
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
            params = request.query_params
            if params:
                q = params.get('q', '') or ''
                # compact filters snapshot
                filters_dict = {k: v for k, v in params.items()}
                ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
                ua = request.META.get('HTTP_USER_AGENT', '')
                SearchQuery.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    q=q[:255],
                    filters=filters_dict,
                    ip=ip,
                    user_agent=ua[:1000],
                )
        except Exception:
            # logging must not break listing
            pass
        return response

    # --- view logging (retrieve) ---
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        try:
            cutoff = timezone.now() - timedelta(hours=VIEW_DEDUP_HOURS)
            ip = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
            ua = request.META.get('HTTP_USER_AGENT', '')

            if request.user.is_authenticated:
                exists = AdView.objects.filter(
                    ad=obj, user=request.user, created_at__gte=cutoff
                ).exists()
                if not exists:
                    AdView.objects.create(
                        ad=obj, user=request.user, ip=ip, user_agent=ua[:1000]
                    )
            else:
                exists = AdView.objects.filter(
                    ad=obj, user__isnull=True, ip=ip, created_at__gte=cutoff
                ).exists()
                if not exists:
                    AdView.objects.create(
                        ad=obj, user=None, ip=ip, user_agent=ua[:1000]
                    )
        except Exception:
            # logging must never block retrieve
            pass

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
        summary="Replace image file (owner only)",
        description="Multipart: field `image` (required), optional `caption` to update together with file.",
        request=None,
        responses={
            200: OpenApiResponse(response=AdImageSerializer),
            400: OpenApiResponse(description="Invalid image or limit exceeded"),
        },
    )
    @action(detail=True, methods=['post'], url_path='replace', parser_classes=[MultiPartParser])
    def replace(self, request, pk=None):
        """
        Replace the image file for an existing AdImage. Owner-only.
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

        # replace file
        obj.image = file

        # optional caption update
        caption = request.data.get('caption')
        if caption is not None:
            obj.caption = caption
        obj.save(update_fields=['image', 'caption'] if caption is not None else ['image'])

        # return fresh representation (with computed URLs)
        return Response(AdImageSerializer(obj, context={'request': request}).data, status=status.HTTP_200_OK)

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
        user = self.request.user
        ad = serializer.validated_data.get('ad')
        if not ad:
            raise ValidationError({"ad": "This field is required."})

        # unique per (tenant, ad)
        if Review.objects.filter(ad=ad, tenant=user).exists():
            raise ValidationError({"detail": "You have already reviewed this ad."})

        # must have a CONFIRMED booking ended in the past
        today = timezone.now().date()
        has_past_confirmed = Booking.objects.filter(
            ad=ad,
            tenant=user,
            status=Booking.CONFIRMED,
            date_to__lt=today
        ).exists()
        if not has_past_confirmed:
            raise ValidationError({"detail": "You can review only after your confirmed booking has finished."})

        serializer.save(tenant=user)


# Helper: cancellation quote calculator (module-level, no indent)
def _compute_cancel_quote(booking):
    """
    Policy:
      - Free: if start is in >= 3 full days.
      - Less than 3 full days left: 20% per each day inside the 3-day window (20/40/60%).
      - Start already reached: no refund (100% fee).

    Total cost is calculated as: daily price * number of nights.
    Assumes `Ad.price` is a per-day price.
    """
    today = timezone.now().date()
    days_until = (booking.date_from - today).days  # full days till start (can be negative)
    FREE_CUTOFF = 3

    # fee % (0.0 .. 1.0)
    if days_until >= FREE_CUTOFF:
        fee_pct = 0.0
    elif days_until >= 0:
        fee_pct = 0.2 * (FREE_CUTOFF - days_until)  # 0.2, 0.4, 0.6
    else:
        fee_pct = 1.0  # after start

    # cost basis
    daily_price = float(getattr(booking.ad, "price", 0) or 0)
    nights = max(1, (booking.date_to - booking.date_from).days)  # treat date_to as checkout date
    total_cost = daily_price * nights
    fee_amount = round(total_cost * fee_pct, 2)

    # user-facing message
    if days_until >= FREE_CUTOFF:
        msg = (
            "Free cancellation is possible only 3 days prior to start date. "
            "Your cancellation fee would be €0.00 (0%)."
        )
    elif days_until >= 0:
        msg = (
            "Free cancellation is possible only 3 days prior to start date; "
            "then 20% of total cost per day. "
            f"Your cancellation fee would be €{fee_amount} ({round(fee_pct*100,2)}%)."
        )
    else:
        msg = (
            "Start date has already begun; no refund is provided. "
            "Are you sure you want to cancel your booking?"
        )

    return {
        "days_until_start": days_until,
        "free_cancellation_cutoff_days": FREE_CUTOFF,
        "fee_percent": round(fee_pct * 100, 2),  # percent value (0–100)
        "fee_amount": fee_amount,
        "currency": "EUR",
        "nights": nights,
        "total_cost": round(total_cost, 2),
        "after_start": days_until < 0,
        "message": msg,
    }


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
        # Only throttle the 'replace' action
        self.throttle_scope = 'adimage_replace' if getattr(self, 'action', None) == 'replace' else None
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
        responses={200: OpenApiResponse(response=AdImageSerializer)},
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

        # replace file
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
@extend_schema(tags=["bookings"])
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

    # Per-action throttling
    throttle_classes = (ScopedRateThrottle,)

    def get_throttles(self):
        # Throttle mutating actions only
        action = getattr(self, 'action', None)
        self.throttle_scope = 'bookings_mutation' if action in ('create', 'confirm', 'reject', 'cancel') else None
        return super().get_throttles()

    def get_queryset(self):
        user = self.request.user
        return Booking.objects.filter(
            Q(tenant=user) | Q(ad__owner=user)
        ).select_related('ad', 'tenant')

    def get_serializer_context(self):
        """Ensure request is in serializer context."""
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def perform_create(self, serializer):
        """
        Set tenant; validation lives in serializer.validate().
        """
        serializer.save(tenant=self.request.user)

    @extend_schema(
        summary="Preview cancellation fee (tenant only)",
        description=(
                "Returns a computed cancellation quote under the current policy:\n"
                "- Free if there are >= 3 full days until start\n"
                "- If < 3 days remain: 20% of total per day that falls inside the 3-day window (20/40/60%)\n"
                "- If the start has already begun: no refund (100% fee)\n\n"
                "Tenant only. Allowed statuses: PENDING, CONFIRMED."
        ),
        responses={200: OpenApiResponse(description="Cancellation quote as JSON")}
    )
    @action(detail=True, methods=['get'], url_path='cancel-quote')
    def cancel_quote(self, request, pk=None):
        booking = self.get_object()

        # Only the tenant can preview/cancel this booking
        if booking.tenant_id != request.user.id:
            raise PermissionDenied("Only the booking tenant can preview/cancel this booking.")

        if booking.status not in (Booking.PENDING, Booking.CONFIRMED):
            return Response({'detail': f'Cannot cancel booking with status {booking.status}.'},
                            status=status.HTTP_400_BAD_REQUEST)

        quote = _compute_cancel_quote(booking)
        return Response(quote, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Cancel booking (tenant only, with fee policy)",
        description=(
                "Tenant only. Cancellation is always allowed, but the fee applies as follows:\n"
                "- Free if there are >= 3 full days until start\n"
                "- If < 3 days remain: 20% per day inside the 3-day window (20/40/60%)\n"
                "- If the start has already begun: no refund (100% fee)\n\n"
                "Response includes the computed `cancel_quote`."
        ),
        responses={
            200: OpenApiResponse(description="Booking cancelled (returns cancel quote)"),
            400: OpenApiResponse(description="Invalid status / already cancelled"),
            403: OpenApiResponse(description="Forbidden (not booking tenant)"),
            404: OpenApiResponse(description="Not found"),
        }
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
            return Response({'detail': f'Cannot cancel booking with status {booking.status}.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Compute the quote (for UI and possible logging)
        quote = _compute_cancel_quote(booking)

        # Apply cancellation
        booking.status = Booking.CANCELLED
        booking.save(update_fields=['status'])

        return Response({'detail': 'Cancelled', 'cancel_quote': quote}, status=status.HTTP_200_OK)

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
        # only ad owner can confirm/reject this booking
        if booking.ad.owner_id != request.user.id:
            raise PermissionDenied("Only the booking owner can confirm this booking.")
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
        # only ad owner can confirm/reject this booking
        if booking.ad.owner_id != request.user.id:
            raise PermissionDenied("Only the booking owner can reject this booking.")
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

    # Throttle search-top endpoint
    throttle_classes = (ScopedRateThrottle,)

    def get_throttles(self):
        self.throttle_scope = 'search_top'
        return super().get_throttles()

    def get(self, request):
        limit = int(request.query_params.get('limit', 10) or 10)
        limit = max(1, min(limit, 50))
        qs = (
            SearchQuery.objects
            .exclude(q='')
            .values('q')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )
        return Response(list(qs), status=status.HTTP_200_OK)
