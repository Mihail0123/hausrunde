from django.db.models import Q, Exists, OuterRef
from django_filters import rest_framework as df
from django.utils.dateparse import parse_date

from ..models import Ad, Booking


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
    lat_max = df.NumberFilter(field_name='latitude', lookup_expr='gte', label='Latitude max')
    lon_min = df.NumberFilter(field_name='longitude', lookup_expr='gte', label='Longitude min')
    lon_max = df.NumberFilter(field_name='longitude', lookup_expr='gte', label='Longitude max')

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
            'mine', 'rating_min', 'rating_max',
            'available_from', 'available_to',
            'lat_min', 'lat_max', 'lon_min', 'lon_max'
        ]
