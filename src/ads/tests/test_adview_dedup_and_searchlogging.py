from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from src.ads.models import Ad, AdView, SearchQuery


class AdViewsAndSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="u@example.com", password="x")
        owner = User.objects.create_user(email="o@example.com", password="x")
        self.ad = Ad.objects.create(
            title="Ad", description="desc", location="Berlin",
            price=100, rooms=2, housing_type="apartment",
            is_active=True, owner=owner
        )
        self.client = APIClient()

    def test_search_logging_list(self):
        # Anonymous list with q
        r = self.client.get("/api/ads/?q=berlin&price_min=500")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(SearchQuery.objects.filter(q="berlin").exists())

        # Authenticated list with q
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/ads/?q=center")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(SearchQuery.objects.filter(q="center", user=self.user).exists())

    def test_view_dedup_authenticated_user(self):
        """Within 6h do not duplicate, after 6h+ create a new AdView (authenticated)."""
        self.client.force_authenticate(self.user)

        # First view -> 1 record
        r1 = self.client.get(f"/api/ads/{self.ad.id}/")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user=self.user).count(), 1)

        # Immediate second view (within 6h) -> still 1 record
        r2 = self.client.get(f"/api/ads/{self.ad.id}/")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user=self.user).count(), 1)

        # Make the existing row older than 6 hours
        AdView.objects.filter(ad=self.ad, user=self.user).update(
            created_at=timezone.now() - timedelta(hours=6, minutes=1)
        )

        # Third view (after 6h+) -> second row appears
        r3 = self.client.get(f"/api/ads/{self.ad.id}/")
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user=self.user).count(), 2)

    def test_view_dedup_anonymous_by_ip(self):
        """Anonymous dedup by IP within 6h; after 6h+ create a new row."""
        headers = {"REMOTE_ADDR": "203.0.113.5", "HTTP_USER_AGENT": "pytest-UA"}

        # First anon view -> 1 record
        r1 = self.client.get(f"/api/ads/{self.ad.id}/", **headers)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user__isnull=True).count(), 1)

        # Immediate second view (within 6h) -> still 1 record
        r2 = self.client.get(f"/api/ads/{self.ad.id}/", **headers)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user__isnull=True).count(), 1)

        # Age the record beyond 6h for that IP
        AdView.objects.filter(ad=self.ad, user__isnull=True).update(
            created_at=timezone.now() - timedelta(hours=6, minutes=1)
        )

        # Third view (after 6h+) -> second row appears
        r3 = self.client.get(f"/api/ads/{self.ad.id}/", **headers)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(AdView.objects.filter(ad=self.ad, user__isnull=True).count(), 2)
