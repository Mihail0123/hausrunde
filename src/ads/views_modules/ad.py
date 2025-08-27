import logging
from django.db.models import Avg, Count
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.utils import timezone
from datetime import timedelta
from django_filters import rest_framework as df

from ..models import Ad, AdView
from ..serializers import AdSerializer
from ..permissions import IsAdOwnerOrReadOnly
from ..pagination import AdPagination
from ..throttling import ScopedRateThrottleIsolated
from .filters import AdFilter

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List ads",
        description="Get paginated list of ads with filtering and search",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Search query"),
            OpenApiParameter("price_min", OpenApiTypes.NUMBER, description="Minimum price"),
            OpenApiParameter("price_max", OpenApiTypes.NUMBER, description="Maximum price"),
            OpenApiParameter("rooms_min", OpenApiTypes.NUMBER, description="Minimum rooms"),
            OpenApiParameter("rooms_max", OpenApiTypes.NUMBER, description="Maximum rooms"),
            OpenApiParameter("location", OpenApiTypes.STR, description="Location contains"),
            OpenApiParameter("housing_type", OpenApiTypes.STR, description="Housing type"),
            OpenApiParameter("area_min", OpenApiTypes.NUMBER, description="Minimum area (m²)"),
            OpenApiParameter("area_max", OpenApiTypes.NUMBER, description="Maximum area (m²)"),
            OpenApiParameter("lat_min", OpenApiTypes.NUMBER, description="Minimum latitude"),
            OpenApiParameter("lat_max", OpenApiTypes.NUMBER, description="Maximum latitude"),
            OpenApiParameter("lon_min", OpenApiTypes.NUMBER, description="Minimum longitude"),
            OpenApiParameter("lon_max", OpenApiTypes.NUMBER, description="Maximum longitude"),
            OpenApiParameter("mine", OpenApiTypes.BOOL, description="Only my ads"),
            OpenApiParameter("rating_min", OpenApiTypes.NUMBER, description="Minimum rating"),
            OpenApiParameter("rating_max", OpenApiTypes.NUMBER, description="Maximum rating"),
            OpenApiParameter("available_from", OpenApiTypes.DATE, description="Available from (YYYY-MM-DD)"),
            OpenApiParameter("available_to", OpenApiTypes.DATE, description="Available to (YYYY-MM-DD)"),
        ],
        responses={
            200: AdSerializer,
            400: OpenApiResponse(description="Invalid filter parameters"),
        }
    ),
    create=extend_schema(
        summary="Create ad",
        description="Create a new ad (authenticated users only)",
        responses={
            201: AdSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
        }
    ),
    retrieve=extend_schema(
        summary="Get ad details",
        description="Get detailed information about a specific ad",
        responses={
            200: AdSerializer,
            404: OpenApiResponse(description="Ad not found"),
        }
    ),
    update=extend_schema(
        summary="Update ad",
        description="Update an existing ad (owner only)",
        responses={
            200: AdSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    ),
    partial_update=extend_schema(
        summary="Partial update ad",
        description="Partially update an existing ad (owner only)",
        responses={
            200: AdSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    ),
    destroy=extend_schema(
        summary="Delete ad",
        description="Delete an ad (owner only)",
        responses={
            204: OpenApiResponse(description="Ad deleted"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    ),
)
class AdViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ads.

    Supports CRUD operations with filtering, search, and pagination.
    """
    serializer_class = AdSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsAdOwnerOrReadOnly)
    pagination_class = AdPagination
    filter_backends = (df.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = AdFilter
    search_fields = ['title', 'description', 'location']
    ordering_fields = ['price', 'created_at', 'average_rating', 'views_count']
    ordering = ['-created_at']
    throttle_classes = [ScopedRateThrottleIsolated]
    throttle_scope = 'ads'

    def get_queryset(self):
        """
        Return ads with optimized queries for common use cases.
        """
        queryset = Ad.objects.select_related('owner').prefetch_related(
            'images', 'reviews__tenant'
        ).annotate(
            average_rating=Avg('reviews__rating'),
            reviews_count=Count('reviews'),
            views_count=Count('adviews')
        )

        # Filter out demo ads for non-owners
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            queryset = queryset.filter(is_demo=False)

        return queryset

    def perform_create(self, serializer):
        """Set the owner to the current user."""
        serializer.save(owner=self.request.user)

    @extend_schema(
        summary="Get ad statistics",
        description="Get statistics for a specific ad (owner only)",
        responses={
            200: OpenApiResponse(
                description="Ad statistics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "total_views": 150,
                            "unique_views": 120,
                            "views_today": 5,
                            "views_this_week": 25,
                            "views_this_month": 80,
                            "average_rating": 4.2,
                            "reviews_count": 8,
                            "bookings_count": 12,
                            "revenue": 2400.0
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request, pk=None):
        """Get detailed statistics for an ad (owner only)."""
        ad = self.get_object()

        # Check if user is the owner
        if ad.owner != request.user:
            return Response(
                {"detail": "You can only view statistics for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Calculate statistics
        stats = {
            'total_views': AdView.objects.filter(ad=ad).count(),
            'unique_views': AdView.objects.filter(ad=ad).values('anon_ip_hash').distinct().count(),
            'views_today': AdView.objects.filter(ad=ad, created_at__date=today).count(),
            'views_this_week': AdView.objects.filter(ad=ad, created_at__date__gte=week_ago).count(),
            'views_this_month': AdView.objects.filter(ad=ad, created_at__date__gte=month_ago).count(),
            'average_rating': ad.average_rating or 0,
            'reviews_count': ad.reviews.count(),
            'bookings_count': ad.bookings.count(),
            'revenue': sum(booking.total_price for booking in ad.bookings.filter(status='confirmed'))
        }

        return Response(stats)

    @extend_schema(
        summary="Toggle ad status",
        description="Activate or deactivate an ad (owner only)",
        responses={
            200: OpenApiResponse(description="Ad status updated"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_status(self, request, pk=None):
        """Toggle ad active/inactive status."""
        ad = self.get_object()

        if ad.owner != request.user:
            return Response(
                {"detail": "You can only modify your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        ad.is_active = not ad.is_active
        ad.save()

        return Response({
            "detail": f"Ad {'activated' if ad.is_active else 'deactivated'} successfully.",
            "is_active": ad.is_active
        })

    @extend_schema(
        summary="Get ad views_modules",
        description="Get view statistics for an ad (owner only)",
        responses={
            200: OpenApiResponse(
                description="Ad view statistics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "total_views": 150,
                            "unique_views": 120,
                            "views_today": 5,
                            "views_this_week": 25,
                            "views_this_month": 80,
                            "recent_views": [
                                {"timestamp": "2024-01-15T10:30:00Z", "ip_hash": "abc123"},
                                {"timestamp": "2024-01-15T09:15:00Z", "ip_hash": "def456"}
                            ]
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def views(self, request, pk=None):
        """Get view statistics for an ad (owner only)."""
        ad = self.get_object()

        if ad.owner != request.user:
            return Response(
                {"detail": "You can only view statistics for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # Get recent views_modules
        recent_views = AdView.objects.filter(ad=ad).order_by('-created_at')[:10]

        stats = {
            'total_views': AdView.objects.filter(ad=ad).count(),
            'unique_views': AdView.objects.filter(ad=ad).values('anon_ip_hash').distinct().count(),
            'views_today': AdView.objects.filter(ad=ad, created_at__date=today).count(),
            'views_this_week': AdView.objects.filter(ad=ad, created_at__date__gte=week_ago).count(),
            'views_this_month': AdView.objects.filter(ad=ad, created_at__date__gte=month_ago).count(),
            'recent_views': [
                {
                    'timestamp': view.created_at,
                    'ip_hash': view.anon_ip_hash
                }
                for view in recent_views
            ]
        }

        return Response(stats)

    @extend_schema(
        summary="Get ad analytics",
        description="Get comprehensive analytics for an ad (owner only)",
        responses={
            200: OpenApiResponse(
                description="Ad analytics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "performance_score": 85.5,
                            "engagement_rate": 12.3,
                            "conversion_rate": 8.7,
                            "top_performing_features": ["location", "price", "images"],
                            "improvement_suggestions": [
                                "Add more high-quality images",
                                "Improve description with keywords",
                                "Consider adjusting price based on market"
                            ]
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Ad not found"),
        }
    )
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def analytics(self, request, pk=None):
        """Get comprehensive analytics for an ad (owner only)."""
        ad = self.get_object()

        if ad.owner != request.user:
            return Response(
                {"detail": "You can only view analytics for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Calculate performance metrics
        total_views = AdView.objects.filter(ad=ad).count()
        total_bookings = ad.bookings.count()
        total_reviews = ad.reviews.count()

        # Performance score (0-100)
        view_score = min(100, total_views * 2)  # Max 50 points for views_modules
        booking_score = min(30, total_bookings * 6)  # Max 30 points for bookings
        review_score = min(20, total_reviews * 4)  # Max 20 points for reviews

        performance_score = view_score + booking_score + review_score

        # Engagement rate (views_modules to interactions ratio)
        engagement_rate = 0
        if total_views > 0:
            interactions = total_bookings + total_reviews
            engagement_rate = (interactions / total_views) * 100

        # Conversion rate (views_modules to bookings ratio)
        conversion_rate = 0
        if total_views > 0:
            conversion_rate = (total_bookings / total_views) * 100

        # Top performing features (simplified analysis)
        top_features = []
        if ad.images.count() > 3:
            top_features.append("images")
        if len(ad.description) > 200:
            top_features.append("description")
        if ad.price and ad.price < 1000:
            top_features.append("price")
        if ad.location and len(ad.location) > 10:
            top_features.append("location")

        # Improvement suggestions
        suggestions = []
        if ad.images.count() < 5:
            suggestions.append("Add more high-quality images")
        if len(ad.description) < 150:
            suggestions.append("Improve description with keywords")
        if not ad.latitude or not ad.longitude:
            suggestions.append("Add precise location coordinates")

        analytics = {
            'performance_score': round(performance_score, 1),
            'engagement_rate': round(engagement_rate, 1),
            'conversion_rate': round(conversion_rate, 1),
            'top_performing_features': top_features,
            'improvement_suggestions': suggestions
        }

        return Response(analytics)
