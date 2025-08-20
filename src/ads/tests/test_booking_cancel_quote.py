from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from src.ads.models import Ad, Booking

class CancelQuoteTests(APITestCase):

    def setUp(self):
        User = get_user_model()
        self.tenant = User.objects.create_user(email="tenant@example.com", password="x")
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.ad = Ad.objects.create(
            owner=self.owner, title="t", description="d", location="L",
            price=Decimal("100.00"), rooms=1, housing_type="apartment", is_active=True
        )
        self.client = APIClient()

    def make_booking(self, start_delta_days, nights=5, status=Booking.CONFIRMED):
        today = timezone.now().date()
        start = today + timedelta(days=start_delta_days)
        end = start + timedelta(days=nights)
        return Booking.objects.create(ad=self.ad, tenant=self.tenant,
                                      date_from=start, date_to=end, status=status)

    def test_free_if_3_plus_days(self):
        self.client.force_authenticate(self.tenant)
        b = self.make_booking(start_delta_days=5, nights=4)
        r = self.client.get(f"/api/bookings/{b.id}/cancel-quote/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fee_percent"], 0)
        self.assertEqual(r.data["fee_amount"], 0)

    def test_60pct_if_start_today(self):
        self.client.force_authenticate(self.tenant)
        b = self.make_booking(start_delta_days=0, nights=5)  # price=100 * 5 nights = 500; 60% -> 300
        r = self.client.get(f"/api/bookings/{b.id}/cancel-quote/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fee_percent"], 60.0)
        self.assertEqual(r.data["fee_amount"], 300.0)
