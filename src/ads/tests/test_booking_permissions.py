from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from src.ads.models import Ad, Booking

class BookingPermissionsTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="o@example.com", password="x")
        self.tenant = User.objects.create_user(email="t@example.com", password="x")
        self.other = User.objects.create_user(email="z@example.com", password="x")
        self.ad = Ad.objects.create(
            title="Ad", description="desc", location="Berlin",
            price=100, rooms=2, housing_type="apartment",
            is_active=True, owner=self.owner
        )
        self.client = APIClient()

    def _make_booking(self, tenant, status=Booking.PENDING, df=None, dt=None):
        df = df or (date.today() + timedelta(days=5))
        dt = dt or (df + timedelta(days=2))
        return Booking.objects.create(ad=self.ad, tenant=tenant, date_from=df, date_to=dt, status=status)

    def test_owner_can_confirm_pending(self):
        b = self._make_booking(self.tenant, status=Booking.PENDING)
        self.client.force_authenticate(self.owner)
        r = self.client.post(f"/api/bookings/{b.id}/confirm/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.CONFIRMED)

    def test_non_owner_cannot_confirm(self):
        """Unrelated user cannot see this booking at all -> 404 from get_queryset filter."""
        b = self._make_booking(self.tenant, status=Booking.PENDING)
        self.client.force_authenticate(self.other)
        r = self.client.post(f"/api/bookings/{b.id}/confirm/")
        self.assertEqual(r.status_code, 404)

    def test_owner_can_reject_pending(self):
        b = self._make_booking(self.tenant, status=Booking.PENDING)
        self.client.force_authenticate(self.owner)
        r = self.client.post(f"/api/bookings/{b.id}/reject/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.CANCELLED)

    def test_tenant_can_cancel_pending(self):
        b = self._make_booking(self.tenant, status=Booking.PENDING)
        self.client.force_authenticate(self.tenant)
        r = self.client.post(f"/api/bookings/{b.id}/cancel/")
        self.assertEqual(r.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.CANCELLED)

    def test_non_tenant_cannot_cancel(self):
        """Unrelated user cannot see this booking at all -> 404."""
        b = self._make_booking(self.tenant, status=Booking.PENDING)
        self.client.force_authenticate(self.other)
        r = self.client.post(f"/api/bookings/{b.id}/cancel/")
        self.assertEqual(r.status_code, 404)
