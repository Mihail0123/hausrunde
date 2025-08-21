# -*- coding: utf-8 -*-
# Booking actions API tests:
# - Owner can confirm/reject a PENDING booking
# - Tenant cannot confirm/reject
# - Tenant can cancel PENDING booking
# Endpoints used:
#   POST /api/bookings/{id}/confirm/
#   POST /api/bookings/{id}/reject/
#   POST /api/bookings/{id}/cancel/

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from src.ads.models import Ad, Booking


class BookingActionsApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(email="owner@example.com", password="x")
        cls.tenant = User.objects.create_user(email="tenant@example.com", password="x")

        cls.ad = Ad.objects.create(
            title="Actions Apartment",
            description="desc",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=cls.owner,
        )
        cls.d1 = date.today() + timedelta(days=5)
        cls.d2 = cls.d1 + timedelta(days=3)

        # Map statuses to support different naming variants in the project
        cls.PENDING = getattr(Booking, "PENDING", "pending")
        cls.CONFIRMED = getattr(Booking, "CONFIRMED", "confirmed")
        cls.CANCELLED = getattr(Booking, "CANCELLED", getattr(Booking, "CANCELED", "cancelled"))
        # Some codebases use DECLINED instead of REJECTED
        cls.REJECTED = getattr(Booking, "REJECTED", getattr(Booking, "DECLINED", "rejected"))

    def _create_pending(self, tenant):
        return Booking.objects.create(
            ad=self.ad,
            tenant=tenant,
            status=self.PENDING,
            date_from=self.d1,
            date_to=self.d2,
        )

    def test_owner_can_confirm_pending(self):
        b = self._create_pending(self.tenant)
        self.client.force_authenticate(self.owner)
        res = self.client.post(f"/api/bookings/{b.id}/confirm/")
        self.assertEqual(res.status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.status, self.CONFIRMED)

    def test_tenant_cannot_confirm_or_reject(self):
        b = self._create_pending(self.tenant)
        self.client.force_authenticate(self.tenant)
        res_c = self.client.post(f"/api/bookings/{b.id}/confirm/")
        res_r = self.client.post(f"/api/bookings/{b.id}/reject/")
        self.assertIn(res_c.status_code, (400, 403))
        self.assertIn(res_r.status_code, (400, 403))
        b.refresh_from_db()
        self.assertEqual(b.status, self.PENDING)

    def test_owner_can_reject_pending(self):
        """Owner rejects a PENDING booking; projects may use REJECTED/DECLINED or CANCELLED."""
        b = self._create_pending(self.tenant)
        self.client.force_authenticate(self.owner)
        res = self.client.post(f"/api/bookings/{b.id}/reject/")
        self.assertEqual(res.status_code, 200)
        b.refresh_from_db()
        # Accept both common variants:
        # - explicit REJECTED/DECLINED status
        # - or mapping the "reject" action to a terminal CANCELLED state
        self.assertIn(b.status, {self.REJECTED, self.CANCELLED})

    def test_tenant_can_cancel_pending(self):
        b = self._create_pending(self.tenant)
        self.client.force_authenticate(self.tenant)
        res = self.client.post(f"/api/bookings/{b.id}/cancel/")
        self.assertIn(res.status_code, (200, 204))
        b.refresh_from_db()
        # After cancel, the booking should not remain pending
        self.assertNotEqual(b.status, self.PENDING)
