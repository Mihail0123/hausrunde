from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from src.ads.models import Ad, Booking

class AvailabilityEndpointTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.tenant = User.objects.create_user(email="tenant@example.com", password="x")
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

        today = date.today()
        # Ranges:
        # PENDING: [D+3 .. D+5]
        # CONFIRMED: [D+7 .. D+9]
        # CANCELLED: [D+11 .. D+13] (must NOT appear)
        Booking.objects.create(
            ad=self.ad, tenant=self.tenant,
            date_from=today + timedelta(days=3),
            date_to=today + timedelta(days=5),
            status=Booking.PENDING,
        )
        Booking.objects.create(
            ad=self.ad, tenant=self.tenant,
            date_from=today + timedelta(days=7),
            date_to=today + timedelta(days=9),
            status=Booking.CONFIRMED,
        )
        Booking.objects.create(
            ad=self.ad, tenant=self.tenant,
            date_from=today + timedelta(days=11),
            date_to=today + timedelta(days=13),
            status=Booking.CANCELLED,
        )

        self.client = APIClient()

    def test_availability_returns_pending_and_confirmed_only(self):
        """Endpoint returns PENDING + CONFIRMED ranges; CANCELLED is excluded."""
        r = self.client.get(f"/api/ads/{self.ad.id}/availability/")
        self.assertEqual(r.status_code, 200)

        data = r.json()
        # Expect exactly 2 items: PENDING and CONFIRMED
        self.assertEqual(len(data), 2)
        statuses = sorted([item["status"] for item in data])
        self.assertEqual(statuses, ["CONFIRMED", "PENDING"])

        # Basic shape check; DRF serializes dates as 'YYYY-MM-DD'
        for item in data:
            self.assertIn("date_from", item)
            self.assertIn("date_to", item)
            self.assertRegex(item["date_from"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertRegex(item["date_to"], r"^\d{4}-\d{2}-\d{2}$")

    def test_filter_by_status_param(self):
        """?status=CONFIRMED returns only confirmed ranges."""
        r = self.client.get(f"/api/ads/{self.ad.id}/availability/?status=CONFIRMED")
        self.assertEqual(r.status_code, 200)

        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "CONFIRMED")
