from django.test import TestCase
from rest_framework.test import APIClient
from src.ads.models import SearchQuery

class SearchTopTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # three 'berlin', two 'paris', one 'rome'
        for _ in range(3):
            SearchQuery.objects.create(q="berlin", filters={})
        for _ in range(2):
            SearchQuery.objects.create(q="paris", filters={})
        SearchQuery.objects.create(q="rome", filters={})

    # empty q should be ignored by (exclude(q=''))

    def test_limit_and_order(self):
        r = self.client.get("/api/search/top/?limit=2")
        self.assertEqual(r.status_code, 200)
        items = r.json()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["q"], "berlin")
        self.assertEqual(items["count"], 3)
        self.assertEqual(items[1]["q"], "paris")
        self.assertEqual(items[1]["count"], 2)

    def test_cap_limit_50(self):
        r = self.client.get("/api/search/top/?limit=999")
        self.assertEqual(r.status_code, 200)
        # in total 3 different q -> returns not more than 3
        self.assertTrue(len(r.json()) <= 50)
