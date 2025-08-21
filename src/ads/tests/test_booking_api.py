from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from src.ads.models import Ad, Booking

User = get_user_model()


@pytest.mark.django_db
class TestBookingAPI:
    def setup_method(self):
        # Test client without JWT; we'll use force_authenticate for simplicity
        self.client = APIClient()

        # Users
        self.owner = User.objects.create_user(email="owner@example.com", password="pass12345")
        self.tenant = User.objects.create_user(email="tenant@example.com", password="pass12345")
        self.other = User.objects.create_user(email="other@example.com", password="pass12345")

        # Active Ad owned by `owner`
        self.ad = Ad.objects.create(
            title="Nice flat",
            description="Test",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="wohnung",
            is_active=True,
            owner=self.owner,
        )

        # Dates
        self.tomorrow = date.today() + timedelta(days=1)
        self.day_after_tomorrow = date.today() + timedelta(days=2)
        self.in_three_days = date.today() + timedelta(days=3)

    # ---------- helpers ----------
    def _auth(self, user):
        """Authenticate client as given user (no JWT required in tests)."""
        self.client.force_authenticate(user=user)

    # ---------- creation rules ----------
    def test_cannot_book_own_ad(self):
        self._auth(self.owner)
        payload = {
            "ad": self.ad.id,
            "date_from": str(self.tomorrow),
            "date_to": str(self.in_three_days),
        }
        resp = self.client.post("/api/bookings/", payload, format="json")
        assert resp.status_code == 400
        assert "cannot book your own ad" in str(resp.data).lower()

    def test_date_from_must_be_tomorrow_and_to_gt_from(self):
        self._auth(self.tenant)

        # date_from == today -> 400
        payload_today = {
            "ad": self.ad.id,
            "date_from": str(date.today()),
            "date_to": str(self.in_three_days),
        }
        resp_today = self.client.post("/api/bookings/", payload_today, format="json")
        assert resp_today.status_code == 400
        assert "tomorrow" in str(resp_today.data).lower()

        # date_to <= date_from -> 400
        payload_wrong_order = {
            "ad": self.ad.id,
            "date_from": str(self.tomorrow),
            "date_to": str(self.tomorrow),
        }
        resp_wrong = self.client.post("/api/bookings/", payload_wrong_order, format="json")
        assert resp_wrong.status_code == 400
        assert "greater than date_from" in str(resp_wrong.data).lower()

    def test_overlaps_consider_confirmed_only(self):
        self._auth(self.tenant)

        # Create a PENDING booking on [tomorrow, in_three_days)
        pending = Booking.objects.create(
            ad=self.ad,
            tenant=self.other,
            date_from=self.tomorrow,
            date_to=self.in_three_days,
            status=Booking.PENDING,
        )

        # Creating another PENDING for the same window must be allowed
        payload_ok = {
            "ad": self.ad.id,
            "date_from": str(self.tomorrow),
            "date_to": str(self.in_three_days),
        }
        resp_ok = self.client.post("/api/bookings/", payload_ok, format="json")
        assert resp_ok.status_code in (200, 201), resp_ok.data

        # Now mark existing booking as CONFIRMED
        pending.status = Booking.CONFIRMED
        pending.save(update_fields=["status"])

        # Try creating new overlapping booking -> must be rejected (overlaps with confirmed)
        payload_overlap = {
            "ad": self.ad.id,
            "date_from": str(self.tomorrow),
            "date_to": str(self.in_three_days),
        }
        resp_overlap = self.client.post("/api/bookings/", payload_overlap, format="json")
        assert resp_overlap.status_code == 400
        assert "overlap" in str(resp_overlap.data).lower()

    # ---------- list projection ----------
    def test_list_contains_denormalized_fields_and_flags(self):
        # Create booking by tenant
        booking = Booking.objects.create(
            ad=self.ad,
            tenant=self.tenant,
            date_from=self.tomorrow,
            date_to=self.in_three_days,
            status=Booking.PENDING,
        )

        # As tenant, should see can_cancel=True, can_cancel_quote=True
        self._auth(self.tenant)
        resp = self.client.get("/api/bookings/?ordering=-id")
        assert resp.status_code == 200

        # Allow both paginated and plain list (depends on your config)
        data = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        assert isinstance(data, list) and len(data) >= 1
        item = data[0]

        # Projection fields
        assert item["ad_id"] == self.ad.id
        assert item["ad_title"] == self.ad.title
        assert item["tenant"]["email"] == self.tenant.email
        assert item["owner"]["email"] == self.owner.email

        # Flags
        assert item["can_cancel"] is True
        assert item["can_cancel_quote"] is True
        assert item["can_confirm"] is False
        assert item["can_reject"] is False
