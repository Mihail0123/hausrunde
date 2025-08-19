from io import BytesIO
from PIL import Image
import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.crypto import get_random_string
from rest_framework.test import APIClient

from src.ads.models import Ad, AdImage


def make_image_bytes(size=(64, 64), color=(200, 100, 50)):
    """Create an in-memory PNG image and return bytes."""
    file = BytesIO()
    img = Image.new("RGB", size, color)
    img.save(file, "PNG")
    file.seek(0)
    return file.read()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="test_media_"))
class AdImageApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.other = User.objects.create_user(email="other@example.com", password="x")

        self.ad = Ad.objects.create(
            title="Ad", description="desc", location="Berlin",
            price=100, rooms=2, housing_type="apartment",
            is_active=True, owner=self.owner
        )

        # create initial image
        png = make_image_bytes()
        self.img = AdImage.objects.create(
            ad=self.ad,
            image=SimpleUploadedFile(f"{get_random_string(6)}.png", png, content_type="image/png"),
            caption="init"
        )

        self.client = APIClient()

    def test_owner_can_patch_caption(self):
        """Owner updates caption via PATCH /api/ad-images/{id}/"""
        self.client.force_authenticate(self.owner)
        r = self.client.patch(f"/api/ad-images/{self.img.id}/", {"caption": "Kitchen"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.img.refresh_from_db()
        self.assertEqual(self.img.caption, "Kitchen")

    def test_non_owner_cannot_patch_caption(self):
        """Non-owner gets 403 on PATCH."""
        self.client.force_authenticate(self.other)
        r = self.client.patch(f"/api/ad-images/{self.img.id}/", {"caption": "hack"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_owner_can_delete(self):
        """Owner can delete; resource returns 204."""
        self.client.force_authenticate(self.owner)
        r = self.client.delete(f"/api/ad-images/{self.img.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(AdImage.objects.filter(pk=self.img.id).exists())

    def test_non_owner_cannot_delete(self):
        """Non-owner gets 403 on DELETE."""
        self.client.force_authenticate(self.other)
        r = self.client.delete(f"/api/ad-images/{self.img.id}/")
        self.assertEqual(r.status_code, 403)

    def test_owner_can_replace_file_and_optionally_caption(self):
        """Owner can POST /replace with new file and new caption."""
        self.client.force_authenticate(self.owner)
        # remember old path
        old_path = self.img.image.path

        new_png = make_image_bytes(size=(80, 80), color=(20, 150, 220))
        payload = {
            "image": SimpleUploadedFile(f"{get_random_string(6)}.png", new_png, content_type="image/png"),
            "caption": "Updated",
        }
        r = self.client.post(f"/api/ad-images/{self.img.id}/replace/", data=payload, format="multipart")
        self.assertEqual(r.status_code, 200)

        self.img.refresh_from_db()
        self.assertEqual(self.img.caption, "Updated")
        self.assertNotEqual(self.img.image.path, old_path)  # new file saved
