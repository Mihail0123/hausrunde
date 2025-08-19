import os
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from src.ads.models import Ad, AdImage


@override_settings(MEDIA_ROOT=None)  # will be set per-test in setUp
class AdImageFileCleanupTests(TestCase):
    def setUp(self):
        # Create a temp media root per test run
        self.tmpdir = TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        # Apply temp MEDIA_ROOT
        self._override = override_settings(MEDIA_ROOT=self.tmpdir.name)
        self._override.enable()
        self.addCleanup(self._override.disable)

        User = get_user_model()
        owner = User.objects.create_user(email="owner@example.com", password="x")
        self.ad = Ad.objects.create(
            title="Ad",
            description="desc",
            location="Berlin",
            price=100,
            rooms=2,
            housing_type="apartment",
            is_active=True,
            owner=owner,
        )

    def _fake_image(self, name="test.jpg", content=b"fake-bytes"):
        return SimpleUploadedFile(name=name, content=content, content_type="image/jpeg")

    def test_delete_removes_file(self):
        img = AdImage.objects.create(ad=self.ad, image=self._fake_image())
        path = img.image.path
        self.assertTrue(os.path.exists(path))

        img.delete()
        self.assertFalse(os.path.exists(path), "File should be removed from storage on delete")

    def test_replace_removes_old_file(self):
        img = AdImage.objects.create(ad=self.ad, image=self._fake_image("old.jpg"))
        old_path = img.image.path
        self.assertTrue(os.path.exists(old_path))

        # Replace the file
        img.image = self._fake_image("new.jpg", b"new-content")
        img.save(update_fields=["image"])

        self.assertFalse(os.path.exists(old_path), "Old file should be removed on replace")
        self.assertTrue(os.path.exists(img.image.path), "New file should exist")
