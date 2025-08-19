from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from src.ads.models import Ad, Booking


class BookingAutoCancelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner   = User.objects.create_user(email="owner@example.com",   password="x")
        self.tenant1 = User.objects.create_user(email="tenant1@example.com", password="x")
        self.tenant2 = User.objects.create_user(email="tenant2@example.com", password="x")

        self.ad = Ad.objects.create(
            title="Apt",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=self.owner,
        )

        # Another ad to ensure cross-ad bookings aren't affected
        self.ad2 = Ad.objects.create(
            title="Apt 2",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=self.owner,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)

        today = date.today()
        # Overlapping window: [D+5 .. D+10]
        self.b1 = Booking.objects.create(
            ad=self.ad, tenant=self.tenant1,
            date_from=today + timedelta(days=5),
            date_to=today + timedelta(days=10),
            status=Booking.PENDING,
        )
        # Overlaps with b1: [D+7 .. D+12]
        self.b2 = Booking.objects.create(
            ad=self.ad, tenant=self.tenant2,
            date_from=today + timedelta(days=7),
            date_to=today + timedelta(days=12),
            status=Booking.PENDING,
        )
        # Same dates on another ad — must not be affected
        self.b3 = Booking.objects.create(
            ad=self.ad2, tenant=self.tenant2,
            date_from=today + timedelta(days=7),
            date_to=today + timedelta(days=12),
            status=Booking.PENDING,
        )

    def test_confirm_auto_cancels_overlapping_pending_on_same_ad(self):
        """Confirming a booking auto-cancels overlapping PENDING bookings on the same ad."""
        r = self.client.post(f"/api/bookings/{self.b1.id}/confirm/")
        self.assertEqual(r.status_code, 200)

        # Refresh from DB
        self.b1.refresh_from_db()
        self.b2.refresh_from_db()
        self.b3.refresh_from_db()

        # Confirmed one becomes CONFIRMED
        self.assertEqual(self.b1.status, Booking.CONFIRMED)
        # Overlapping pending on same ad becomes CANCELLED
        self.assertEqual(self.b2.status, Booking.CANCELLED)
        # Booking on another ad remains intact
        self.assertEqual(self.b3.status, Booking.PENDING)

    def test_non_overlapping_pending_is_not_cancelled(self):
        """Non-overlapping pending bookings on same ad are not cancelled."""
        today = date.today()
        # Non-overlapping window: [D+11 .. D+13] (starts after b1 ends D+10)
        b4 = Booking.objects.create(
            ad=self.ad, tenant=self.tenant2,
            date_from=today + timedelta(days=11),
            date_to=today + timedelta(days=13),
            status=Booking.PENDING,
        )
        r = self.client.post(f"/api/bookings/{self.b1.id}/confirm/")
        self.assertEqual(r.status_code, 200)
        b4.refresh_from_db()
        self.assertEqual(b4.status, Booking.PENDING)
