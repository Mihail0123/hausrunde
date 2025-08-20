from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from src.ads.models import Ad, AdImage

def make_image_bytes(size=(64, 64), color=(200, 100, 50)):
    file = BytesIO()
    img = Image.new("RGB", size, color)
    img.save(file, "PNG")
    file.seek(0)
    return file.read()

@override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_CLASSES': []})  # отключаем троттлинг
class AdImageApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.other = User.objects.create_user(email="other@example.com", password="x")
        self.ad = Ad.objects.create(
            title="Ad",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=self.owner,
        )

        png = make_image_bytes()
        self.img = AdImage.objects.create(
            ad=self.ad,
            image=SimpleUploadedFile("test.png", png, content_type="image/png"),
            caption="init"
        )
        self.client = APIClient()

    def test_owner_can_patch_caption(self):
        self.client.force_authenticate(self.owner)
        r = self.client.patch(f"/api/ad-images/{self.img.id}/", {"caption": "Kitchen"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.img.refresh_from_db()
        self.assertEqual(self.img.caption, "Kitchen")

    def test_non_owner_cannot_patch_caption(self):
        self.client.force_authenticate(self.other)
        r = self.client.patch(f"/api/ad-images/{self.img.id}/", {"caption": "hack"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_owner_can_delete(self):
        self.client.force_authenticate(self.owner)
        r = self.client.delete(f"/api/ad-images/{self.img.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(AdImage.objects.filter(pk=self.img.id).exists())

    def test_non_owner_cannot_delete(self):
        self.client.force_authenticate(self.other)
        r = self.client.delete(f"/api/ad-images/{self.img.id}/")
        self.assertEqual(r.status_code, 403)

    def test_owner_can_replace_file_and_optionally_caption(self):
        self.client.force_authenticate(self.owner)
        old_path = self.img.image.path
        new_png = make_image_bytes(size=(80, 80), color=(20, 150, 220))
        payload = {
            "image": SimpleUploadedFile("new.png", new_png, content_type="image/png"),
            "caption": "Updated",
        }
        r = self.client.post(f"/api/ad-images/{self.img.id}/replace/", data=payload, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.img.refresh_from_db()
        self.assertEqual(self.img.caption, "Updated")
        self.assertNotEqual(self.img.image.path, old_path)
