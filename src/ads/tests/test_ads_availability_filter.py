from datetime import date
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from src.ads.models import Ad, Booking

User = get_user_model()

class AdsAvailabilityFilterTests(TestCase):
    """Tests for ?available_from / ?available_to filter on /api/ads/."""

    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            email="owner@example.com", password="x"
        )
        self.tenant = User.objects.create_user(
            email="tenant@example.com", password="x"
        )

        # Two active ads owned by the same owner
        self.ad1 = Ad.objects.create(
            owner=self.owner,
            title="Ad with overlap",
            description="Should be excluded when window overlaps booking",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="apartment",
            area=50,
            is_active=True,
        )
        self.ad2 = Ad.objects.create(
            owner=self.owner,
            title="Ad without overlap",
            description="Should remain in results",
            location="Berlin",
            price=900,
            rooms=1,
            housing_type="apartment",
            area=40,
            is_active=True,
        )

        # Create a CONFIRMED booking on ad1 for 2025-09-07 .. 2025-09-08
        Booking.objects.create(
            ad=self.ad1,
            tenant=self.tenant,
            date_from=date(2025, 9, 7),
            date_to=date(2025, 9, 8),
            status=Booking.CONFIRMED,
        )

        # Non-overlapping pending booking for ad2 (not required but ok)
        Booking.objects.create(
            ad=self.ad2,
            tenant=self.tenant,
            date_from=date(2025, 9, 20),
            date_to=date(2025, 9, 22),
            status=Booking.PENDING,
        )

    def _get_ids(self, payload):
        """Extract list of ad IDs from paginated or plain list response."""
        if isinstance(payload, dict) and "results" in payload:
            items = payload["results"]
        else:
            items = payload
        return [it["id"] for it in items]

    def test_includes_ads_when_no_overlap(self):
        """
        Window 2025-09-01..2025-09-05 does NOT overlap ad1 booking (7..8).
        Expect both ads present.
        """
        r = self.client.get(
            "/api/ads/",
            {"available_from": "2025-09-01", "available_to": "2025-09-05"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        ids = self._get_ids(r.json())
        self.assertIn(self.ad1.id, ids)
        self.assertIn(self.ad2.id, ids)

    def test_excludes_ads_with_overlapping_bookings(self):
        """
        Window 2025-09-07..2025-09-10 overlaps ad1 booking (7..8).
        Expect ad1 excluded; ad2 still present.
        """
        r = self.client.get(
            "/api/ads/",
            {"available_from": "2025-09-07", "available_to": "2025-09-10"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        ids = self._get_ids(r.json())
        self.assertNotIn(self.ad1.id, ids)
        self.assertIn(self.ad2.id, ids)
