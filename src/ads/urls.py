from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views_modules import (
    AdViewSet, BookingViewSet, ReviewViewSet, AdImageViewSet,
    SearchHistoryTopView,
)

app_name = "ads"

router = DefaultRouter()
router.register(r"ads", AdViewSet, basename="ad")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"ad-images", AdImageViewSet, basename="adimage")

urlpatterns = [
    path("", include(router.urls)),
    path("search/top/", SearchHistoryTopView.as_view(), name="search-top"),
]


