from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AdViewSet, BookingViewSet, ReviewViewSet, AdImageViewSet, SearchHistoryTopView

app_name = "ads"

router = DefaultRouter()
router.register(r"ads", AdViewSet)
router.register(r"bookings", BookingViewSet)
router.register(r"reviews", ReviewViewSet)
router.register(r"ad-images", AdImageViewSet, basename="ad-images")

urlpatterns = [
    *router.urls,
    # Keep the public stats endpoint. Provide two paths for backward compatibility.
    path("search/top/", SearchHistoryTopView.as_view(), name="search-top"),
    path("search-history/top/", SearchHistoryTopView.as_view(), name="search-history-top"),
]
