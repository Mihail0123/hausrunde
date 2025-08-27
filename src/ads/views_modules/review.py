import logging
from django.db.models import Avg
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import (
    extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.utils import timezone
from datetime import timedelta

from ..models import Review
from ..serializers import ReviewSerializer
from ..permissions import IsReviewOwnerOrAdmin

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List reviews",
        description="Get list of reviews with filtering",
        parameters=[
            OpenApiParameter("ad", OpenApiTypes.INT, description="Filter by ad ID"),
            OpenApiParameter("tenant", OpenApiTypes.INT, description="Filter by tenant ID"),
            OpenApiParameter("rating", OpenApiTypes.INT, description="Filter by rating"),
        ],
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Invalid parameters"),
        }
    ),
    create=extend_schema(
        summary="Create review",
        description="Create a new review (authenticated users only)",
        request=ReviewSerializer,
        responses={
            201: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
        }
    ),
    retrieve=extend_schema(
        summary="Get review details",
        description="Get detailed information about a specific review",
        responses={
            200: ReviewSerializer,
            404: OpenApiResponse(description="Review not found"),
        }
    ),
    update=extend_schema(
        summary="Update review",
        description="Update an existing review (owner only)",
        request=ReviewSerializer,
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        }
    ),
    partial_update=extend_schema(
        summary="Partial update review",
        description="Partially update an existing review (owner only)",
        request=ReviewSerializer,
        responses={
            200: ReviewSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        }
    ),
    destroy=extend_schema(
        summary="Delete review",
        description="Delete a review (owner or admin only)",
        responses={
            204: OpenApiResponse(description="Review deleted"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Review not found"),
        }
    ),
)
class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing reviews.

    Supports CRUD operations with user-based permissions.
    """
    serializer_class = ReviewSerializer
    permission_classes = (permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrAdmin)
    throttle_scope = 'reviews'

    def get_queryset(self):
        """Filter reviews based on query parameters."""
        queryset = Review.objects.select_related('tenant', 'ad__owner')

        # Filter by ad
        ad_id = self.request.query_params.get('ad')
        if ad_id:
            try:
                ad_id = int(ad_id)
                queryset = queryset.filter(ad_id=ad_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid ad ID: {ad_id}")
                return Review.objects.none()

        # Filter by tenant
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id:
            try:
                tenant_id = int(tenant_id)
                queryset = queryset.filter(tenant_id=tenant_id)
            except (ValueError, TypeError):
                logger.warning(f"Invalid tenant ID: {tenant_id}")
                return Review.objects.none()

        # Filter by rating
        rating = self.request.query_params.get('rating')
        if rating:
            try:
                rating = int(rating)
                if 1 <= rating <= 5:
                    queryset = queryset.filter(rating=rating)
            except (ValueError, TypeError):
                logger.warning(f"Invalid rating: {rating}")

        return queryset

    def perform_create(self, serializer):
        """Set the tenant to the current user."""
        serializer.save(tenant=self.request.user)

    @extend_schema(
        summary="Get review statistics",
        description="Get statistics for reviews",
        parameters=[
            OpenApiParameter("ad", OpenApiTypes.INT, description="Filter by ad ID"),
        ],
        responses={
            200: OpenApiResponse(
                description="Review statistics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "total_reviews": 45,
                            "average_rating": 4.2,
                            "rating_distribution": {
                                "1": 2,
                                "2": 3,
                                "3": 8,
                                "4": 20,
                                "5": 12
                            },
                            "recent_reviews": 15
                        }
                    )
                ]
            ),
        }
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get review statistics."""
        ad_id = request.query_params.get('ad')

        if ad_id:
            try:
                ad_id = int(ad_id)
                queryset = Review.objects.filter(ad_id=ad_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid ad ID."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            queryset = Review.objects.all()

        # Calculate statistics
        total_reviews = queryset.count()
        average_rating = queryset.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

        # Rating distribution
        rating_distribution = {}
        for rating in range(1, 6):
            rating_distribution[str(rating)] = queryset.filter(rating=rating).count()

        # Recent reviews (last 30 days)
        recent_date = timezone.now().date() - timedelta(days=30)
        recent_reviews = queryset.filter(created_at__date__gte=recent_date).count()

        stats = {
            'total_reviews': total_reviews,
            'average_rating': round(average_rating, 1),
            'rating_distribution': rating_distribution,
            'recent_reviews': recent_reviews
        }

        return Response(stats)

    @extend_schema(
        summary="Get review trends",
        description="Get review trends over time",
        parameters=[
            OpenApiParameter("ad", OpenApiTypes.INT, description="Filter by ad ID"),
            OpenApiParameter("period", OpenApiTypes.STR, description="Time period (week, month, year)"),
        ],
        responses={
            200: OpenApiResponse(
                description="Review trends",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "period": "month",
                            "trends": [
                                {"date": "2024-01-01", "count": 5, "avg_rating": 4.2},
                                {"date": "2024-01-08", "count": 8, "avg_rating": 4.5},
                                {"date": "2024-01-15", "count": 3, "avg_rating": 3.8}
                            ]
                        }
                    )
                ]
            ),
        }
    )
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get review trends over time."""
        ad_id = request.query_params.get('ad')
        period = request.query_params.get('period', 'month')

        if ad_id:
            try:
                ad_id = int(ad_id)
                queryset = Review.objects.filter(ad_id=ad_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid ad ID."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            queryset = Review.objects.all()

        # Determine time period
        if period == 'week':
            days = 7
        elif period == 'month':
            days = 30
        elif period == 'year':
            days = 365
        else:
            return Response(
                {"detail": "Invalid period. Use 'week', 'month', or 'year'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate trends
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        trends = []
        current_date = start_date

        while current_date <= end_date:
            if period == 'week':
                period_start = current_date
                period_end = current_date + timedelta(days=6)
            elif period == 'month':
                period_start = current_date
                period_end = current_date + timedelta(days=29)
            else:  # year
                period_start = current_date
                period_end = current_date + timedelta(days=364)

            period_reviews = queryset.filter(
                created_at__date__gte=period_start,
                created_at__date__lte=period_end
            )

            count = period_reviews.count()
            avg_rating = period_reviews.aggregate(avg=Avg('rating'))['avg'] or 0

            trends.append({
                'date': current_date.isoformat(),
                'count': count,
                'avg_rating': round(avg_rating, 1)
            })

            if period == 'week':
                current_date += timedelta(days=7)
            elif period == 'month':
                current_date += timedelta(days=30)
            else:
                current_date += timedelta(days=365)

        return Response({
            'period': period,
            'trends': trends
        })
