# src/ads/tests/test_ads_bbox_filter.py

from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from src.ads.models import Ad

User = get_user_model()

class AdsBBoxFilterTests(TestCase):
    """Tests for bbox filters: lat_min/lat_max/lon_min/lon_max."""

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(email="o@example.com", password="x")

        # Inside Berlin-ish bbox
        self.ad_inside = Ad.objects.create(
            owner=self.owner,
            title="Inside bbox",
            description="Should be included",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="apartment",
            area=50,
            is_active=True,
            latitude=52.52,
            longitude=13.405,
        )

        # Outside bbox (far away)
        self.ad_outside = Ad.objects.create(
            owner=self.owner,
            title="Outside bbox",
            description="Should be excluded",
            location="Munich",
            price=1100,
            rooms=2,
            housing_type="apartment",
            area=55,
            is_active=True,
            latitude=48.137,
            longitude=11.575,
        )

    def _ids(self, payload):
        # Handle paginated and plain list responses
        items = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        return [it["id"] for it in items]

    def test_bbox_includes_only_inside(self):
        """Only items within provided bbox should be returned."""
        params = {
            "lat_min": 52.3,
            "lat_max": 52.7,
            "lon_min": 13.2,
            "lon_max": 13.6,
        }
        r = self.client.get("/api/ads/", params, format="json")
        self.assertEqual(r.status_code, 200)
        ids = self._ids(r.json())
        self.assertIn(self.ad_inside.id, ids)
        self.assertNotIn(self.ad_outside.id, ids)

    def test_bbox_partial_filters_work(self):
        """
        Partial bbox is still valid: min-only or max-only should narrow results.
        Example: only lat_min cuts out southern cities.
        """
        r = self.client.get("/api/ads/", {"lat_min": 50.0}, format="json")
        self.assertEqual(r.status_code, 200)
        ids = self._ids(r.json())
        self.assertIn(self.ad_inside.id, ids)
        self.assertNotIn(self.ad_outside.id, ids)
