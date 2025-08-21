# -*- coding: utf-8 -*-
# Contract tests for /api/ads/
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from src.ads.models import Ad


REQUIRED_FIELDS = {
    "id", "title", "location", "housing_type", "price", "rooms", "area",
    "is_active", "latitude", "longitude", "average_rating", "reviews_count",
    "views_count", "owner_id",
}


class AdsApiContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        owner = User.objects.create_user(email="owner@example.com", password="x")
        # минимально одно объявление, чтобы список не был пустой
        Ad.objects.create(
            title="Contract Ad",
            description="desc",
            location="Berlin",
            price=1000,
            rooms=2,
            housing_type="apartment",  # корректное значение из твоих choices
            is_active=True,
            owner=owner,
            area=50,
            latitude=52.52,
            longitude=13.405,
        )

    def _extract_results(self, data):
        # совместимо с пагинацией DRF и без неё
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_list_has_required_fields_and_pagination(self):
        url = reverse("ads:ad-list")
        res = self.client.get(url, {"page_size": 1})
        self.assertEqual(res.status_code, 200)

        # Считаем, что включена пагинация DRF: есть count и results
        if isinstance(res.data, dict):
            self.assertIn("count", res.data)
            self.assertIn("results", res.data)

        items = self._extract_results(res.data)
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 1)

        ad = items[0]
        missing = REQUIRED_FIELDS - set(ad.keys())
        self.assertFalse(missing, f"Missing fields: {missing}")

    def test_ordering_supported(self):
        url = reverse("ads:ad-list")
        # проверяем, что параметр ordering не взрывает и возвращает 200
        for field in ["price", "-price", "average_rating", "-average_rating", "views_count", "-views_count"]:
            res = self.client.get(url, {"ordering": field, "page_size": 1})
            self.assertEqual(res.status_code, 200)
