from django.test import override_settings
from rest_framework.test import APITestCase
from django.urls import reverse

TEST_THROTTLE_RATES = {
    'ads_list': '2/min',
    'ads_availability': '2/min',
    'auth_login': '2/min',
}

@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': TEST_THROTTLE_RATES
    }
)
class AdsThrottleTests(APITestCase):
    def test_ads_list_throttling(self):
        # Используем namespace "ads" и имя "ad-list" из списка URL
        url = reverse('ads:ad-list')
        r1 = self.client.get(url)
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)

        r3 = self.client.get(url)
        self.assertEqual(r3.status_code, 429)

    def test_availability_throttling(self):
        from src.ads.models import Ad
        from django.contrib.auth import get_user_model

        User = get_user_model()
        owner = User.objects.create_user(email='owner@example.com', password='x')

        ad = Ad.objects.create(
            title='Test Ad',
            description='desc',
            location='Berlin',
            price=100,
            rooms=1,
            housing_type='apartment',
            is_active=True,
            owner=owner,
        )

        url = reverse('ads:ad-availability', args=[ad.id])
        r1 = self.client.get(url)
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.get(url)
        self.assertEqual(r2.status_code, 200)

        r3 = self.client.get(url)
        self.assertEqual(r3.status_code, 429)


@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': TEST_THROTTLE_RATES
    }
)
class AuthThrottleTests(APITestCase):
    def test_login_throttling(self):
        url = reverse('token_obtain_pair')

        data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword",
        }

        r1 = self.client.post(url, data)
        self.assertEqual(r1.status_code, 401)

        r2 = self.client.post(url, data)
        self.assertEqual(r2.status_code, 401)

        r3 = self.client.post(url, data)
        self.assertEqual(r3.status_code, 429)
