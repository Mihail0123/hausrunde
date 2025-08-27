import logging
from datetime import timedelta

from django.db.models import Q, Avg, F
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from drf_spectacular.utils import (
    extend_schema_view, extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.utils import timezone

from ..models import Booking
from ..serializers import BookingSerializer
from ..permissions import IsBookingOwnerOrAdOwner

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List bookings",
        description="Get list of bookings (filtered by user role)",
        parameters=[
            OpenApiParameter("as_tenant", OpenApiTypes.BOOL, description="Show bookings as tenant"),
            OpenApiParameter("as_owner", OpenApiTypes.BOOL, description="Show bookings as ad owner"),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by status"),
        ],
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Invalid parameters"),
        }
    ),
    create=extend_schema(
        summary="Create booking",
        description="Create a new booking (authenticated users only)",
        request=BookingSerializer,
        responses={
            201: BookingSerializer,
            400: OpenApiResponse(description="Validation error"),
            401: OpenApiResponse(description="Authentication required"),
        }
    ),
    retrieve=extend_schema(
        summary="Get booking details",
        description="Get detailed information about a specific booking",
        responses={
            200: BookingSerializer,
            404: OpenApiResponse(description="Booking not found"),
        }
    ),
    update=extend_schema(
        summary="Update booking",
        description="Update an existing booking (limited fields)",
        request=BookingSerializer,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    ),
    partial_update=extend_schema(
        summary="Partial update booking",
        description="Partially update an existing booking",
        request=BookingSerializer,
        responses={
            200: BookingSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    ),
    destroy=extend_schema(
        summary="Cancel booking",
        description="Cancel a booking (tenant or owner)",
        responses={
            204: OpenApiResponse(description="Booking cancelled"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    ),
)
class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing bookings.

    Supports CRUD operations with role-based permissions and status management.
    """
    serializer_class = BookingSerializer
    permission_classes = (permissions.IsAuthenticated, IsBookingOwnerOrAdOwner)
    throttle_scope = 'bookings'

    def get_queryset(self):
        """Filter bookings based on user role."""
        user = self.request.user

        # Staff can see all bookings
        if user.is_staff:
            return Booking.objects.select_related('ad__owner', 'tenant')

        # Regular users see their own bookings (as tenant or owner)
        return Booking.objects.filter(
            Q(tenant=user) | Q(ad__owner=user)
        ).select_related('ad__owner', 'tenant')

    def perform_create(self, serializer):
        """Set the tenant to the current user."""
        serializer.save(tenant=self.request.user)

    @extend_schema(
        summary="Confirm booking",
        description="Confirm a pending booking (ad owner only)",
        responses={
            200: OpenApiResponse(description="Booking confirmed"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def confirm(self, request, pk=None):
        """Confirm a pending booking."""
        booking = self.get_object()

        if booking.ad.owner != request.user:
            raise PermissionDenied("Only the ad owner can confirm bookings.")

        if booking.status != Booking.PENDING:
            raise ValidationError({"status": "Only pending bookings can be confirmed."})

        booking.status = Booking.CONFIRMED
        booking.save()

        return Response({"detail": "Booking confirmed successfully."})

    @extend_schema(
        summary="Reject booking",
        description="Reject a pending booking (ad owner only)",
        responses={
            200: OpenApiResponse(description="Booking rejected"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def reject(self, request, pk=None):
        """Reject a pending booking."""
        booking = self.get_object()

        if booking.ad.owner != request.user:
            raise PermissionDenied("Only the ad owner can reject bookings.")

        if booking.status != Booking.PENDING:
            raise ValidationError({"status": "Only pending bookings can be rejected."})

        booking.status = Booking.REJECTED
        booking.save()

        return Response({"detail": "Booking rejected successfully."})

    @extend_schema(
        summary="Cancel booking",
        description="Cancel a confirmed booking (tenant only)",
        responses={
            200: OpenApiResponse(description="Booking cancelled"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Booking not found"),
        }
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def cancel(self, request, pk=None):
        """Cancel a confirmed booking."""
        booking = self.get_object()

        if booking.tenant != request.user:
            raise PermissionDenied("Only the tenant can cancel bookings.")

        if booking.status not in [Booking.PENDING, Booking.CONFIRMED]:
            raise ValidationError({"status": "Only pending or confirmed bookings can be cancelled."})

        # Check if it's too late to cancel
        if booking.date_from <= timezone.now().date():
            raise ValidationError({"date_from": "Cannot cancel bookings that have already started."})

        booking.status = Booking.CANCELLED
        booking.save()

        return Response({"detail": "Booking cancelled successfully."})

    @extend_schema(
        summary="Get booking statistics",
        description="Get statistics for bookings (owner only)",
        responses={
            200: OpenApiResponse(
                description="Booking statistics",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "total_bookings": 25,
                            "confirmed_bookings": 18,
                            "pending_bookings": 5,
                            "cancelled_bookings": 2,
                            "total_revenue": 4500.0,
                            "average_booking_duration": 3.2
                        }
                    )
                ]
            ),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def stats(self, request):
        """Get booking statistics for the current user."""
        user = request.user

        if user.is_staff:
            # Staff can see all statistics
            queryset = Booking.objects.all()
        else:
            # Regular users see their own ad statistics
            queryset = Booking.objects.filter(ad__owner=user)

        stats = {
            'total_bookings': queryset.count(),
            'confirmed_bookings': queryset.filter(status=Booking.CONFIRMED).count(),
            'pending_bookings': queryset.filter(status=Booking.PENDING).count(),
            'cancelled_bookings': queryset.filter(status=Booking.CANCELLED).count(),
            'total_revenue': sum(b.total_price for b in queryset.filter(status=Booking.CONFIRMED)),
            'average_booking_duration': queryset.filter(status=Booking.CONFIRMED).aggregate(
                avg_duration=Avg(F('date_to') - F('date_from'))
            )['avg_duration'] or 0
        }

        return Response(stats)

    @extend_schema(
        summary="Get booking calendar",
        description="Get calendar view of bookings for an ad (owner only)",
        parameters=[
            OpenApiParameter("ad_id", OpenApiTypes.INT, description="Ad ID", required=True),
            OpenApiParameter("year", OpenApiTypes.INT, description="Year (YYYY)"),
            OpenApiParameter("month", OpenApiTypes.INT, description="Month (1-12)"),
        ],
        responses={
            200: OpenApiResponse(
                description="Booking calendar",
                examples=[
                    OpenApiExample(
                        "Example response",
                        value={
                            "year": 2024,
                            "month": 1,
                            "bookings": [
                                {
                                    "date_from": "2024-01-15",
                                    "date_to": "2024-01-18",
                                    "status": "confirmed",
                                    "tenant_email": "user@example.com"
                                }
                            ]
                        }
                    )
                ]
            ),
            400: OpenApiResponse(description="Invalid parameters"),
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def calendar(self, request):
        """Get calendar view of bookings for an ad."""
        ad_id = request.query_params.get('ad_id')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not ad_id:
            return Response(
                {"detail": "ad_id parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            ad_id = int(ad_id)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid ad_id parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify user owns the ad
        from ..models import Ad
        try:
            ad = Ad.objects.get(id=ad_id)
        except Ad.DoesNotExist:
            return Response(
                {"detail": "Ad not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if ad.owner != request.user:
            return Response(
                {"detail": "You can only view calendar for your own ads."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get current year/month if not specified
        if not year or not month:
            now = timezone.now()
            year = int(year) if year else now.year
            month = int(month) if month else now.month

        # Get bookings for the specified month
        from datetime import date
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        bookings = Booking.objects.filter(
            ad_id=ad_id,
            date_from__lte=end_date,
            date_to__gte=start_date
        ).select_related('tenant')

        calendar_data = {
            'year': year,
            'month': month,
            'bookings': [
                {
                    'date_from': booking.date_from.isoformat(),
                    'date_to': booking.date_to.isoformat(),
                    'status': booking.status,
                    'tenant_email': booking.tenant.email if booking.tenant else None
                }
                for booking in bookings
            ]
        }

        return Response(calendar_data)
