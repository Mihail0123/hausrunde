from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from src.ads.models import Ad, Booking
from src.ads.serializers import BookingSerializer

class BookingValidationTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.tenant = User.objects.create_user(email="tenant@example.com", password="x")

        self.ad_active = Ad.objects.create(
            title="Active Ad",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=self.owner,
        )

        self.ad_inactive = Ad.objects.create(
            title="Inactive Ad",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=False,
            owner=self.owner,
        )

    def _ctx(self, user):
        class DummyReq:
            def __init__(self, u):
                self.user = u
        return {"request": DummyReq(user)}

    def test_date_order_required(self):
        df = date.today()
        dt = df  # invalid: same day
        s = BookingSerializer(
            data={"ad": self.ad_active.id, "date_from": df, "date_to": dt},
            context=self._ctx(self.tenant),
        )
        self.assertFalse(s.is_valid())
        self.assertIn("date_to", s.errors)

    def test_cannot_book_inactive_ad(self):
        df = date.today()
        dt = df + timedelta(days=2)
        s = BookingSerializer(
            data={"ad": self.ad_inactive.id, "date_from": df, "date_to": dt},
            context=self._ctx(self.tenant),
        )
        self.assertFalse(s.is_valid())
        self.assertIn("ad", s.errors)

    def test_cannot_book_own_ad(self):
        df = date.today()
        dt = df + timedelta(days=2)
        s = BookingSerializer(
            data={"ad": self.ad_active.id, "date_from": df, "date_to": dt},
            context=self._ctx(self.owner),  # owner tries to book own ad
        )
        self.assertFalse(s.is_valid())
        self.assertIn("non_field_errors", s.errors)

    def test_overlap_is_rejected(self):
        # Existing confirmed booking
        df = date.today() + timedelta(days=5)
        dt = df + timedelta(days=5)
        Booking.objects.create(
            ad=self.ad_active, tenant=self.tenant,
            date_from=df, date_to=dt, status=Booking.CONFIRMED,
        )

        # New booking overlapping existing
        s = BookingSerializer(
            data={
                "ad": self.ad_active.id,
                "date_from": df + timedelta(days=2),
                "date_to": dt + timedelta(days=2),
            },
            context=self._ctx(get_user_model().objects.create_user(email="other@example.com", password="x")),
        )
        self.assertFalse(s.is_valid())
        self.assertIn("non_field_errors", s.errors)

    def test_non_overlapping_is_ok(self):
        df = date.today() + timedelta(days=5)
        dt = df + timedelta(days=5)
        Booking.objects.create(
            ad=self.ad_active, tenant=self.tenant,
            date_from=df, date_to=dt, status=Booking.CONFIRMED,
        )

        # New booking after the previous ends (no overlap)
        s = BookingSerializer(
            data={
                "ad": self.ad_active.id,
                "date_from": dt + timedelta(days=1),
                "date_to": dt + timedelta(days=3),
            },
            context=self._ctx(get_user_model().objects.create_user(email="ok@example.com", password="x")),
        )
        self.assertTrue(s.is_valid(), msg=s.errors)
