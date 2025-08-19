# src/ads/tests/test_throttling.py
from django.test import TestCase
from django.conf import settings as dj_settings
from django.urls import reverse, NoReverseMatch
from rest_framework.test import APIClient
from rest_framework.settings import api_settings as drf_api_settings
from src.users.models import CustomUser
from src.ads.models import Ad


def _reverse_any(candidates, kwargs=None):
    last_err = None
    for name in candidates:
        try:
            return reverse(name, kwargs=kwargs or {})
        except NoReverseMatch as e:
            last_err = e
    raise last_err or NoReverseMatch(f"No candidates resolved: {candidates!r}")


class _ThrottleRatesOverrideMixin:
    def _enable_rates_override(self, rates_patch: dict):
        rf = dict(dj_settings.REST_FRAMEWORK)
        merged_rates = dict(rf.get("DEFAULT_THROTTLE_RATES", {}))
        merged_rates.update(rates_patch)
        rf["DEFAULT_THROTTLE_RATES"] = merged_rates
        self._ctx = self.settings(REST_FRAMEWORK=rf)
        self._ctx.enable()
        # VERY IMPORTANT: force DRF to re-read settings
        drf_api_settings.reload()

    def _disable_rates_override(self):
        if hasattr(self, "_ctx"):
            self._ctx.disable()
            drf_api_settings.reload()


class AdsThrottleTests(TestCase, _ThrottleRatesOverrideMixin):
    def setUp(self):
        # Make limits very small to hit 429 on the 3rd request
        self._enable_rates_override({
            "ads_list": "2/min",
            "ads_availability": "2/min",
            "ads_retrieve": "2/min",
        })
        self.client = APIClient()
        # Fix client IP so throttle keys are stable for anon
        self.client.defaults["REMOTE_ADDR"] = "9.9.9.9"

        owner = CustomUser.objects.create_user(email="o@example.com", password="x")
        self.ad = Ad.objects.create(
            title="t", description="d", location="loc",
            price=10, rooms=1, housing_type="apartment",
            owner=owner, is_active=True
        )

        self.url_list = _reverse_any(["ad-list", "ads:ad-list", "ads-list"])
        self.url_avail = _reverse_any(
            ["ad-availability", "ads:ad-availability", "ads-availability"],
            kwargs={"pk": self.ad.pk},
        )

    def tearDown(self):
        self._disable_rates_override()

    def test_ads_list_throttled(self):
        r1 = self.client.get(self.url_list)
        r2 = self.client.get(self.url_list)
        r3 = self.client.get(self.url_list)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 429)

    def test_availability_throttled(self):
        r1 = self.client.get(self.url_avail)
        r2 = self.client.get(self.url_avail)
        r3 = self.client.get(self.url_avail)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r3.status_code, 429)


class AuthThrottleTests(TestCase, _ThrottleRatesOverrideMixin):
    def setUp(self):
        self._enable_rates_override({"auth_login": "2/min"})
        self.client = APIClient()
        self.client.defaults["REMOTE_ADDR"] = "8.8.8.8"
        self.url_login = _reverse_any(["login", "users:login"])
        CustomUser.objects.create_user(email="u@example.com", password="correct")

    def tearDown(self):
        self._disable_rates_override()

    def test_login_throttled(self):
        payload = {"email": "u@example.com", "password": "wrong"}
        r1 = self.client.post(self.url_login, payload, format="json")
        r2 = self.client.post(self.url_login, payload, format="json")
        r3 = self.client.post(self.url_login, payload, format="json")
        # First two may be 401 (bad creds) but must pass
        self.assertIn(r1.status_code, (200, 401))
        self.assertIn(r2.status_code, (200, 401))
        # Third must be throttled
        self.assertEqual(r3.status_code, 429)
