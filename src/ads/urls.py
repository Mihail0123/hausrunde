from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AdViewSet, BookingViewSet, ReviewViewSet, AdImageViewSet, SearchHistoryTopView

app_name = "ads"

router = DefaultRouter()
router.register(r"", AdViewSet, basename="ad")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"ad-images", AdImageViewSet, basename="ad-images")

urlpatterns = [
    *router.urls,
    path("search/top/", SearchHistoryTopView.as_view(), name="search-top"),
    path("search-history/top/", SearchHistoryTopView.as_view(), name="search-history-top"),
]
