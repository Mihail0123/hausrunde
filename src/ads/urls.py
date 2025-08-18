from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdViewSet, BookingViewSet, ReviewViewSet,
    SearchHistoryTopView,
)

router = DefaultRouter()
router.register(r'ads', AdViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'reviews', ReviewViewSet)

urlpatterns = [
    *router.urls,
    path('search-history/top/', SearchHistoryTopView.as_view(), name='search-history-top'),
]
