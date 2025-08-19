from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from src.ads.models import Ad


class AdValidationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="o@example.com", password="x")
        self.other = User.objects.create_user(email="z@example.com", password="x")
        self.ad = Ad.objects.create(
            title="Ad", description="desc", location="Berlin",
            price=100, rooms=2, housing_type="apartment",
            is_active=True, owner=self.owner
        )
        self.client = APIClient()

    def _patch(self, payload, as_owner=True):
        if as_owner:
            self.client.force_authenticate(self.owner)
        else:
            self.client.force_authenticate(self.other)
        return self.client.patch(f"/api/ads/{self.ad.id}/", payload, format="json")

    # ---- non-negative numbers ----
    def test_price_must_be_non_negative(self):
        r = self._patch({"price": -1})
        self.assertEqual(r.status_code, 400)
        self.assertIn("price", r.data)

    def test_rooms_must_be_non_negative(self):
        r = self._patch({"rooms": -2})
        self.assertEqual(r.status_code, 400)
        self.assertIn("rooms", r.data)

    def test_area_must_be_non_negative(self):
        r = self._patch({"area": -10})
        self.assertEqual(r.status_code, 400)
        self.assertIn("area", r.data)

    # ---- latitude/longitude ranges ----
    def test_latitude_range(self):
        r = self._patch({"latitude": 95})
        self.assertEqual(r.status_code, 400)
        self.assertIn("latitude", r.data)

        r2 = self._patch({"latitude": -95})
        self.assertEqual(r2.status_code, 400)
        self.assertIn("latitude", r2.data)

        r_ok = self._patch({"latitude": 52.52})
        self.assertEqual(r_ok.status_code, 200)

    def test_longitude_range(self):
        r = self._patch({"longitude": 200})
        self.assertEqual(r.status_code, 400)
        self.assertIn("longitude", r.data)

        r2 = self._patch({"longitude": -200})
        self.assertEqual(r2.status_code, 400)
        self.assertIn("longitude", r2.data)

        r_ok = self._patch({"longitude": 13.405})
        self.assertEqual(r_ok.status_code, 200)

    # Optional: non-owner cannot patch (should be 403 or 404 based on IsAdOwnerOrReadOnly)
    def test_non_owner_cannot_patch(self):
        r = self._patch({"price": 123}, as_owner=False)
        self.assertIn(r.status_code, (403, 404))
