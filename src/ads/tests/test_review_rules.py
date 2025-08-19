from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from src.ads.models import Ad, Booking


class ReviewRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.tenant = User.objects.create_user(email="tenant@example.com", password="x")
        self.other  = User.objects.create_user(email="other@example.com",  password="x")

        self.ad = Ad.objects.create(
            title="Nice flat",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=self.owner,
        )

        self.client = APIClient()

    def _login(self, who):
        self.client.force_authenticate(who)

    def _post_review(self, rating=5, text="ok"):
        return self.client.post("/api/reviews/", {
            "ad": self.ad.id,
            "rating": rating,
            "text": text,
        }, format="json")

    def test_cannot_review_without_confirmed_past_booking(self):
        """User without a past CONFIRMED booking cannot post a review."""
        self._login(self.tenant)
        r = self._post_review()
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.data)

    def test_cannot_review_before_checkout_even_if_confirmed(self):
        """Booking is CONFIRMED but future checkout -> still forbidden."""
        self._login(self.tenant)
        today = date.today()
        Booking.objects.create(
            ad=self.ad,
            tenant=self.tenant,
            date_from=today + timedelta(days=1),
            date_to=today + timedelta(days=3),  # future
            status=Booking.CONFIRMED,
        )
        r = self._post_review()
        self.assertEqual(r.status_code, 400)
        self.assertIn("detail", r.data)

    def test_can_review_after_confirmed_past_booking(self):
        """Past CONFIRMED booking allows leaving a review."""
        self._login(self.tenant)
        today = date.today()
        Booking.objects.create(
            ad=self.ad,
            tenant=self.tenant,
            date_from=today - timedelta(days=5),
            date_to=today - timedelta(days=2),  # past
            status=Booking.CONFIRMED,
        )
        r = self._post_review(rating=4, text="good")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data.get("rating"), 4)

    def test_only_one_review_per_tenant_ad(self):
        """Second review for the same (tenant, ad) is rejected."""
        self._login(self.tenant)
        today = date.today()
        Booking.objects.create(
            ad=self.ad,
            tenant=self.tenant,
            date_from=today - timedelta(days=5),
            date_to=today - timedelta(days=2),
            status=Booking.CONFIRMED,
        )
        # first ok
        r1 = self._post_review(rating=5)
        self.assertEqual(r1.status_code, 201)
        # second rejected
        r2 = self._post_review(rating=3)
        self.assertEqual(r2.status_code, 400)
        self.assertIn("detail", r2.data)

    def test_owner_cannot_review_own_ad(self):
        """Owner shouldn't be able to review their own ad (no eligible booking)."""
        self._login(self.owner)
        r = self._post_review()
        # either 400 due to booking rule, or 403 if custom rule — but not 201
        self.assertIn(r.status_code, (400, 403))
