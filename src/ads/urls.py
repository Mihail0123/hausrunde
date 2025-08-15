from rest_framework.routers import DefaultRouter

from .views import AdViewSet, BookingViewSet

router = DefaultRouter()
router.register(r'ads', AdViewSet)
router.register(r'bookings', BookingViewSet)

urlpatterns = router.urls