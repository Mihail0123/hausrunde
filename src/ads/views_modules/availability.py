import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta, date

from ..models import Booking, Ad
from ..serializers import AvailabilityItemSerializer

logger = logging.getLogger(__name__)


@extend_schema(
    summary="Get ad availability",
    description="Get availability information for a specific ad",
    parameters=[
        OpenApiParameter("ad_id", OpenApiTypes.INT, description="Ad ID", required=True),
        OpenApiParameter("from_date", OpenApiTypes.DATE, description="Start date (YYYY-MM-DD)"),
        OpenApiParameter("to_date", OpenApiTypes.DATE, description="End date (YYYY-MM-DD)"),
    ],
    responses={
        200: AvailabilityItemSerializer,
        400: OpenApiResponse(description="Invalid parameters"),
        404: OpenApiResponse(description="Ad not found"),
    }
)
class AvailabilityView(APIView):
    """
    API view for checking ad availability.

    Shows booked dates and available periods for a specific ad.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Get availability information for an ad."""
        ad_id = request.query_params.get('ad_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')

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

        # Check if ad exists
        try:
            ad = Ad.objects.get(id=ad_id, is_active=True)
        except Ad.DoesNotExist:
            return Response(
                {"detail": "Ad not found or inactive."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Parse date range
        if from_date and to_date:
            try:
                from_date = parse_date(from_date)
                to_date = parse_date(to_date)

                if not from_date or not to_date:
                    raise ValueError("Invalid date format")

                if from_date >= to_date:
                    return Response(
                        {"detail": "from_date must be before to_date."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default to next 30 days if no range specified
            from_date = timezone.now().date()
            to_date = from_date + timedelta(days=30)

        # Get all bookings for the ad in the date range
        bookings = Booking.objects.filter(
            ad=ad,
            date_from__lte=to_date,
            date_to__gte=from_date
        ).order_by('date_from')

        # Create availability items
        availability_items = []
        for booking in bookings:
            # Adjust dates to fit within requested range
            start_date = max(booking.date_from, from_date)
            end_date = min(booking.date_to, to_date)

            availability_items.append({
                'date_from': start_date,
                'date_to': end_date,
                'status': booking.status
            })

        # If no bookings, the entire period is available
        if not availability_items:
            availability_items.append({
                'date_from': from_date,
                'date_to': to_date,
                'status': 'available'
            })

        serializer = AvailabilityItemSerializer(availability_items, many=True)
        return Response(serializer.data)


@extend_schema(
    summary="Get bulk availability",
    description="Get availability for multiple ads at once",
    request=OpenApiTypes.OBJECT,
    responses={
        200: OpenApiResponse(
            description="Bulk availability results",
            examples=[
                OpenApiExample(
                    "Example response",
                    value={
                        "results": [
                            {
                                "ad_id": 1,
                                "availability": [
                                    {"date_from": "2024-01-15", "date_to": "2024-01-18", "status": "confirmed"}
                                ]
                            }
                        ]
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid request data"),
    }
)
class BulkAvailabilityView(APIView):
    """
    API view for getting availability for multiple ads.

    Useful for comparing availability across multiple properties.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Get availability for multiple ads."""
        ad_ids = request.data.get('ad_ids', [])
        from_date = request.data.get('from_date')
        to_date = request.data.get('to_date')

        if not ad_ids:
            return Response(
                {"detail": "ad_ids parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(ad_ids, list):
            return Response(
                {"detail": "ad_ids must be a list."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse date range
        if from_date and to_date:
            try:
                from_date = parse_date(from_date)
                to_date = parse_date(to_date)

                if not from_date or not to_date:
                    raise ValueError("Invalid date format")

                if from_date >= to_date:
                    return Response(
                        {"detail": "from_date must be before to_date."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default to next 30 days
            from_date = timezone.now().date()
            to_date = from_date + timedelta(days=30)

        # Validate ad IDs
        try:
            ad_ids = [int(ad_id) for ad_id in ad_ids]
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid ad_id values in ad_ids list."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get active ads
        ads = Ad.objects.filter(id__in=ad_ids, is_active=True)
        if not ads:
            return Response(
                {"detail": "No active ads found with the provided IDs."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get availability for each ad
        results = []
        for ad in ads:
            bookings = Booking.objects.filter(
                ad=ad,
                date_from__lte=to_date,
                date_to__gte=from_date
            ).order_by('date_from')

            availability_items = []
            for booking in bookings:
                start_date = max(booking.date_from, from_date)
                end_date = min(booking.date_to, to_date)

                availability_items.append({
                    'date_from': start_date,
                    'date_to': end_date,
                    'status': booking.status
                })

            # If no bookings, mark as available
            if not availability_items:
                availability_items.append({
                    'date_from': from_date,
                    'date_to': to_date,
                    'status': 'available'
                })

            results.append({
                'ad_id': ad.id,
                'ad_title': ad.title,
                'availability': availability_items
            })

        return Response({
            'results': results,
            'date_range': {
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat()
            }
        })


@extend_schema(
    summary="Get availability calendar",
    description="Get monthly calendar view of availability for an ad",
    parameters=[
        OpenApiParameter("ad_id", OpenApiTypes.INT, description="Ad ID", required=True),
        OpenApiParameter("year", OpenApiTypes.INT, description="Year (YYYY)"),
        OpenApiParameter("month", OpenApiTypes.INT, description="Month (1-12)"),
    ],
    responses={
        200: OpenApiResponse(
            description="Availability calendar",
            examples=[
                OpenApiExample(
                    "Example response",
                    value={
                        "year": 2024,
                        "month": 1,
                        "calendar": [
                            {"date": "2024-01-01", "status": "available"},
                            {"date": "2024-01-02", "status": "booked"},
                            {"date": "2024-01-03", "status": "booked"}
                        ]
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid parameters"),
        404: OpenApiResponse(description="Ad not found"),
    }
)
class AvailabilityCalendarView(APIView):
    """
    API view for getting monthly availability calendar.

    Provides a calendar view showing daily availability status.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Get monthly availability calendar."""
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

        # Check if ad exists
        try:
            ad = Ad.objects.get(id=ad_id, is_active=True)
        except Ad.DoesNotExist:
            return Response(
                {"detail": "Ad not found or inactive."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get current year/month if not specified
        if not year or not month:
            now = timezone.now()
            year = int(year) if year else now.year
            month = int(month) if month else now.month

        try:
            year = int(year)
            month = int(month)
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid year or month parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not (1 <= month <= 12):
            return Response(
                {"detail": "Month must be between 1 and 12."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate month boundaries
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # Get bookings for the month
        bookings = Booking.objects.filter(
            ad=ad,
            date_from__lte=end_date,
            date_to__gte=start_date
        )

        # Create calendar
        calendar = []
        current_date = start_date

        while current_date <= end_date:
            # Check if date is booked
            is_booked = False
            for booking in bookings:
                if booking.date_from <= current_date <= booking.date_to:
                    is_booked = True
                    break

            calendar.append({
                'date': current_date.isoformat(),
                'status': 'booked' if is_booked else 'available'
            })

            current_date += timedelta(days=1)

        return Response({
            'year': year,
            'month': month,
            'ad_id': ad_id,
            'ad_title': ad.title,
            'calendar': calendar
        })
