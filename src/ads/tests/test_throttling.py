from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from src.ads.models import Ad

# For tests we only *lower the rates* for the specific scopes we hit.
# We must MERGE into existing REST_FRAMEWORK so that throttle classes remain enabled.
TEST_RATES = {
    "ads_list": "2/min",
    "ads_availability": "2/min",
    "auth_login": "2/min",
}

RF_MERGED = {
    **settings.REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
        **TEST_RATES,
    },
}


@override_settings(REST_FRAMEWORK=RF_MERGED)
class AdsThrottleTests(APITestCase):

    def test_ads_list_throttling(self):
        """Third anonymous GET to ad-list should be throttled (429)."""
        url = reverse("ads:ad-list")
        r1 = self.client.get(url)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)
        r3 = self.client.get(url)
        self.assertEqual(r3.status_code, 429)

    def test_availability_throttling(self):
        """Third anonymous GET to ad-availability should be throttled (429)."""
        User = get_user_model()
        owner = User.objects.create_user(email="owner@example.com", password="x")
        ad = Ad.objects.create(
            title="Test Ad",
            description="desc",
            location="Berlin",
            price=100,
            rooms=1,
            housing_type="apartment",
            is_active=True,
            owner=owner,
        )
        url = reverse("ads:ad-availability", args=[ad.id])
        r1 = self.client.get(url)
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)
        r3 = self.client.get(url)
        self.assertEqual(r3.status_code, 429)


@override_settings(REST_FRAMEWORK=RF_MERGED)
class AuthThrottleTests(APITestCase):

    def test_login_throttling(self):
        """Third POST with wrong creds should be throttled (429) on auth_login scope."""
        url = reverse("token_obtain_pair")
        payload = {"email": "nonexistent@example.com", "password": "wrongpassword"}

        r1 = self.client.post(url, payload)
        self.assertEqual(r1.status_code, 401)  # wrong creds
        r2 = self.client.post(url, payload)
        self.assertEqual(r2.status_code, 401)
        r3 = self.client.post(url, payload)
        self.assertEqual(r3.status_code, 429)
