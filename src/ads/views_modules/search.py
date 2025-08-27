import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes,
    OpenApiExample, OpenApiResponse
)
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from ..models import SearchQuery, Ad, AdView
from ..throttling import ScopedRateThrottleIsolated

logger = logging.getLogger(__name__)


@extend_schema(
    summary="Get search history and top searches",
    description="Get popular search queries and user's search history",
    parameters=[
        OpenApiParameter("days", OpenApiTypes.INT, description="Number of days to look back", default=30),
        OpenApiParameter("limit", OpenApiTypes.INT, description="Maximum number of results", default=10),
    ],
    responses={
        200: OpenApiResponse(
            description="Search statistics",
            examples=[
                OpenApiExample(
                    "Example response",
                    value={
                        "top_searches": [
                            {"query": "apartment berlin", "count": 45},
                            {"query": "studio near center", "count": 32},
                            {"query": "2 bedroom flat", "count": 28}
                        ],
                        "recent_searches": [
                            {"query": "apartment berlin", "timestamp": "2024-01-15T10:30:00Z"},
                            {"query": "studio near center", "timestamp": "2024-01-14T15:20:00Z"}
                        ],
                        "trending_searches": [
                            {"query": "student housing", "growth": 25.5},
                            {"query": "short term rental", "growth": 18.2}
                        ]
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid parameters"),
    }
)
class SearchHistoryTopView(APIView):
    """
    API view for getting search history and top searches.

    Provides insights into popular search patterns and user behavior.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    throttle_classes = [ScopedRateThrottleIsolated]
    throttle_scope = 'search'

    def get(self, request):
        """Get search statistics and history."""
        try:
            days = int(request.query_params.get('days', 30))
            limit = int(request.query_params.get('limit', 10))
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid days or limit parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if days < 1 or days > 365:
            return Response(
                {"detail": "Days must be between 1 and 365."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if limit < 1 or limit > 100:
            return Response(
                {"detail": "Limit must be between 1 and 100."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Get top searches in the period
        top_searches = SearchQuery.objects.filter(
            created_at__gte=start_date
        ).values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        # Get recent searches for the current user
        recent_searches = []
        if request.user.is_authenticated:
            recent_searches = SearchQuery.objects.filter(
                user=request.user,
                created_at__gte=start_date
            ).values('query', 'created_at').order_by('-created_at')[:limit]

        # Calculate trending searches (comparing two periods)
        half_period = days // 2
        first_half_start = start_date
        first_half_end = start_date + timedelta(days=half_period)
        second_half_start = first_half_end
        second_half_end = end_date

        # Get search counts for both periods
        first_half_counts = {}
        second_half_counts = {}

        for sq in SearchQuery.objects.filter(created_at__gte=start_date):
            if first_half_start <= sq.created_at < first_half_end:
                first_half_counts[sq.query] = first_half_counts.get(sq.query, 0) + 1
            elif second_half_start <= sq.created_at <= second_half_end:
                second_half_counts[sq.query] = second_half_counts.get(sq.query, 0) + 1

        # Calculate growth rates
        trending_searches = []
        for query in set(first_half_counts.keys()) | set(second_half_counts.keys()):
            first_count = first_half_counts.get(query, 0)
            second_count = second_half_counts.get(query, 0)

            if first_count > 0:
                growth = ((second_count - first_count) / first_count) * 100
                if abs(growth) >= 10:  # Only show significant changes
                    trending_searches.append({
                        'query': query,
                        'growth': round(growth, 1)
                    })

        # Sort by absolute growth
        trending_searches.sort(key=lambda x: abs(x['growth']), reverse=True)
        trending_searches = trending_searches[:limit]

        return Response({
            'top_searches': list(top_searches),
            'recent_searches': list(recent_searches),
            'trending_searches': trending_searches
        })

    def post(self, request):
        """Log a search query."""
        query = request.data.get('query')
        ad_id = request.data.get('ad_id')

        if not query:
            return Response(
                {"detail": "Query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create search query log
        search_query = SearchQuery.objects.create(
            query=query,
            user=request.user if request.user.is_authenticated else None,
            ad_id=ad_id
        )

        return Response({
            "detail": "Search query logged successfully.",
            "id": search_query.id
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Get search suggestions",
    description="Get search suggestions based on popular queries and user input",
    parameters=[
        OpenApiParameter("q", OpenApiTypes.STR, description="Partial search query", required=True),
        OpenApiParameter("limit", OpenApiTypes.INT, description="Maximum number of suggestions", default=5),
    ],
    responses={
        200: OpenApiResponse(
            description="Search suggestions",
            examples=[
                OpenApiExample(
                    "Example response",
                    value={
                        "suggestions": [
                            "apartment berlin",
                            "apartment berlin center",
                            "apartment berlin mitte",
                            "apartment berlin kreuzberg",
                            "apartment berlin charlottenburg"
                        ]
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Missing query parameter"),
    }
)
class SearchSuggestionsView(APIView):
    """
    API view for getting search suggestions.

    Provides autocomplete suggestions based on popular searches and partial input.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottleIsolated]
    throttle_scope = 'search_suggestions'

    def get(self, request):
        """Get search suggestions."""
        query = request.query_params.get('q')
        limit = int(request.query_params.get('limit', 5))

        if not query:
            return Response(
                {"detail": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(query) < 2:
            return Response({
                "suggestions": []
            })

        # Get suggestions from recent searches
        recent_suggestions = SearchQuery.objects.filter(
            query__icontains=query
        ).values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:limit]

        # Get suggestions from ad titles and locations
        ad_suggestions = Ad.objects.filter(
            Q(title__icontains=query) | Q(location__icontains=query),
            is_active=True
        ).values('title', 'location')[:limit]

        # Combine and rank suggestions
        suggestions = set()

        # Add recent search suggestions
        for item in recent_suggestions:
            suggestions.add(item['query'])

        # Add ad-based suggestions
        for ad in ad_suggestions:
            if query.lower() in ad['title'].lower():
                suggestions.add(ad['title'])
            if query.lower() in ad['location'].lower():
                suggestions.add(ad['location'])

        # Convert to list and limit
        suggestions_list = list(suggestions)[:limit]

        return Response({
            "suggestions": suggestions_list
        })


@extend_schema(
    summary="Get search analytics",
    description="Get detailed analytics about search patterns",
    parameters=[
        OpenApiParameter("days", OpenApiTypes.INT, description="Number of days to analyze", default=30),
        OpenApiParameter("ad_id", OpenApiTypes.INT, description="Filter by specific ad"),
    ],
    responses={
        200: OpenApiResponse(
            description="Search analytics",
            examples=[
                OpenApiExample(
                    "Example response",
                    value={
                        "total_searches": 1250,
                        "unique_users": 450,
                        "popular_queries": [
                            {"query": "apartment", "count": 156},
                            {"query": "studio", "count": 89},
                            {"query": "berlin", "count": 67}
                        ],
                        "search_trends": [
                            {"date": "2024-01-01", "searches": 45},
                            {"date": "2024-01-02", "searches": 52}
                        ],
                        "conversion_rate": 12.5
                    }
                )
            ]
        ),
        400: OpenApiResponse(description="Invalid parameters"),
    }
)
class SearchAnalyticsView(APIView):
    """
    API view for getting search analytics.

    Provides detailed insights into search patterns and user behavior.
    """
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottleIsolated]
    throttle_scope = 'search_analytics'

    def get(self, request):
        """Get search analytics."""
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid days parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if days < 1 or days > 365:
            return Response(
                {"detail": "Days must be between 1 and 365."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ad_id = request.query_params.get('ad_id')

        # Calculate date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Base queryset
        search_queryset = SearchQuery.objects.filter(created_at__gte=start_date)

        if ad_id:
            try:
                ad_id = int(ad_id)
                search_queryset = search_queryset.filter(ad_id=ad_id)
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid ad_id parameter."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Calculate analytics
        total_searches = search_queryset.count()
        unique_users = search_queryset.filter(user__isnull=False).values('user').distinct().count()

        # Popular queries
        popular_queries = search_queryset.values('query').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Search trends over time
        trends = []
        current_date = start_date

        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            daily_searches = search_queryset.filter(
                created_at__date=current_date
            ).count()

            trends.append({
                'date': current_date.isoformat(),
                'searches': daily_searches
            })

            current_date = next_date

        # Conversion rate (searches that led to ad views_modules)
        if ad_id:
            # For specific ad, calculate conversion from searches to views_modules
            searches_count = search_queryset.count()
            views_count = AdView.objects.filter(
                ad_id=ad_id,
                created_at__gte=start_date
            ).count()

            conversion_rate = (views_count / searches_count * 100) if searches_count > 0 else 0
        else:
            # Overall conversion rate
            total_searches_all_time = SearchQuery.objects.count()
            total_views_all_time = AdView.objects.count()
            conversion_rate = (
                        total_views_all_time / total_searches_all_time * 100) if total_searches_all_time > 0 else 0

        analytics = {
            'total_searches': total_searches,
            'unique_users': unique_users,
            'popular_queries': list(popular_queries),
            'search_trends': trends,
            'conversion_rate': round(conversion_rate, 1)
        }

        return Response(analytics)
