# -*- coding: utf-8 -*-
# Contract tests for /api/bookings/
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from src.ads.models import Ad, Booking


REQUIRED_FIELDS = {
    "id", "ad", "ad_id", "ad_title", "tenant", "owner",
    "date_from", "date_to", "status",
    "can_cancel", "can_cancel_quote", "can_confirm", "can_reject",
}


class BookingsApiContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(email="owner@example.com", password="x")
        cls.tenant = User.objects.create_user(email="tenant@example.com", password="x")

        cls.ad = Ad.objects.create(
            title="Bookable",
            description="desc",
            location="Berlin",
            price=1200,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=cls.owner,
        )
        cls.tomorrow = date.today() + timedelta(days=1)
        cls.after = cls.tomorrow + timedelta(days=2)

    def setUp(self):
        self.client.force_authenticate(user=self.tenant)

    def _extract_results(self, data):
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_list_contains_required_projection_fields(self):
        # создаём бронирование
        payload = {"ad": self.ad.id, "date_from": str(self.tomorrow), "date_to": str(self.after)}
        create = self.client.post(reverse("ads:booking-list"), payload, format="json")
        self.assertIn(create.status_code, (200, 201), create.data)

        res = self.client.get(reverse("ads:booking-list"), {"page_size": 1})
        self.assertEqual(res.status_code, 200)

        items = self._extract_results(res.data)
        self.assertGreaterEqual(len(items), 1)
        b = items[0]

        missing = REQUIRED_FIELDS - set(b.keys())
        self.assertFalse(missing, f"Missing fields: {missing}")

        # вложенные tenant/owner — объекты {id,email}
        self.assertIn("id", b["tenant"])
        self.assertIn("email", b["tenant"])
        self.assertIn("id", b["owner"])
        self.assertIn("email", b["owner"])
