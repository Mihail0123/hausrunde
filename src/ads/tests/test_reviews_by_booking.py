from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test.utils import override_settings
from django.conf import settings

from src.ads.models import Ad, Booking, Review

User = get_user_model()


@pytest.mark.django_db
class TestReviewsByBooking:
    def setup_method(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(email="owner@example.com", password="p")
        self.tenant = User.objects.create_user(email="tenant@example.com", password="p")

        self.ad = Ad.objects.create(
            title="Flat",
            description="x",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="wohnung",
            is_active=True,
            owner=self.owner,
        )

        today = date.today()
        self.d1 = today - timedelta(days=10)
        self.d2 = today - timedelta(days=7)
        self.d3 = today - timedelta(days=5)
        self.d4 = today - timedelta(days=2)

        # Two finished CONFIRMED bookings by the same tenant for same ad
        self.b1 = Booking.objects.create(ad=self.ad, tenant=self.tenant, status=Booking.CONFIRMED,
                                         date_from=self.d1, date_to=self.d2)
        self.b2 = Booking.objects.create(ad=self.ad, tenant=self.tenant, status=Booking.CONFIRMED,
                                         date_from=self.d3, date_to=self.d4)

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    @override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
                # Raise only the generic user limit so three POSTs do not hit 429 here
                "user": "100/minute",
            },
        }
    )
    def test_create_review_binds_to_latest_finished_confirmed_booking(self):
        # Authenticate as tenant
        self._auth(self.tenant)

        # First review should bind to the latest finished confirmed booking (b2)
        r1 = self.client.post("/api/reviews/", {"ad": self.ad.id, "rating": 5, "comment": "Good"}, format="json")
        assert r1.status_code in (200, 201), r1.data
        rev1 = Review.objects.get(pk=r1.data["id"])
        assert rev1.booking_id == self.b2.id
        assert rev1.text == "Good"

        # Second review should bind to the previous finished booking (b1)
        r2 = self.client.post("/api/reviews/", {"ad": self.ad.id, "rating": 4, "text": "Ok"}, format="json")
        assert r2.status_code in (200, 201), r2.data
        rev2 = Review.objects.get(pk=r2.data["id"])
        assert rev2.booking_id == self.b1.id
        assert rev2.text == "Ok"

        # Third attempt -> no eligible bookings left -> expect business 400 (not 429)
        r3 = self.client.post("/api/reviews/", {"ad": self.ad.id, "rating": 3, "comment": "meh"}, format="json")
        assert r3.status_code == 400

    def test_cannot_review_before_finish(self):
        # Ensure there are no finished confirmed bookings for this user/ad in this scenario
        Booking.objects.filter(ad=self.ad, tenant=self.tenant, status=Booking.CONFIRMED).delete()

        # Future booking, even if CONFIRMED
        future_from = date.today() + timedelta(days=1)
        future_to = date.today() + timedelta(days=3)
        Booking.objects.create(ad=self.ad, tenant=self.tenant, status=Booking.CONFIRMED,
                               date_from=future_from, date_to=future_to)

        self._auth(self.tenant)
        resp = self.client.post("/api/reviews/", {"ad": self.ad.id, "rating": 5, "comment": "nope"}, format="json")
        assert resp.status_code == 400