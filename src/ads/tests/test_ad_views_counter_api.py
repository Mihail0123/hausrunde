# -*- coding: utf-8 -*-
# Views counter on retrieve:
# - Detail response exposes "views_count" (int)
# - Second GET should return value >= first (some implementations increment once per session/TTL)

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from src.ads.models import Ad


class AdViewsCounterApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        owner = User.objects.create_user(email="owner@example.com", password="x")
        cls.ad = Ad.objects.create(
            title="Viewed Ad",
            description="desc",
            location="Berlin",
            price=900,
            rooms=1,
            housing_type="apartment",
            is_active=True,
            owner=owner,
        )

    def test_retrieve_exposes_and_increments_views_count(self):
        url = f"/api/ads/{self.ad.id}/"
        r1 = self.client.get(url)
        self.assertEqual(r1.status_code, 200)
        self.assertIn("views_count", r1.data)
        self.assertIsInstance(r1.data["views_count"], int)

        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)
        self.assertIn("views_count", r2.data)
        # Allow equal (if dedup/TTL) or increased value
        self.assertGreaterEqual(r2.data["views_count"], r1.data["views_count"])
