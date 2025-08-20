from io import BytesIO
from PIL import Image
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from src.ads.models import Ad, AdImage


def make_image_bytes(w=50, h=50, fmt="JPEG"):
    buf = BytesIO()
    img = Image.new("RGB", (w, h), color=(123, 123, 123))
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf.getvalue()


class AdImageConstraintsTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(email="owner@example.com", password="x")
        self.other = User.objects.create_user(email="other@example.com", password="x")
        self.ad = Ad.objects.create(
            owner=self.owner,
            title="t", description="d", location="loc",
            price=Decimal("100.00"), rooms=2, housing_type="apartment",
            is_active=True
        )
        self.client = APIClient()

    @override_settings(AD_IMAGES_MAX_PER_AD=2)
    def test_limit_per_ad(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/ads/{self.ad.id}/images/"
        files = [
            SimpleUploadedFile("a1.jpg", make_image_bytes(), content_type="image/jpeg"),
            SimpleUploadedFile("a2.jpg", make_image_bytes(), content_type="image/jpeg"),
        ]
        resp = self.client.post(url, data={"images": files}, format="multipart")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AdImage.objects.filter(ad=self.ad).count(), 2)

        # try to add third -> 400
        files2 = [SimpleUploadedFile("a3.jpg", make_image_bytes(), content_type="image/jpeg")]
        resp2 = self.client.post(url, data={"images": files2}, format="multipart")
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("Too many images", resp2.data.get("detail", ""))

    @override_settings(AD_IMAGE_ALLOWED_FORMATS={"JPEG"})
    def test_reject_unsupported_format(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/ads/{self.ad.id}/images/"
        png = SimpleUploadedFile("pic.png", make_image_bytes(fmt="PNG"), content_type="image/png")
        resp = self.client.post(url, data={"images": [png]}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported format", str(resp.data))

    @override_settings(AD_IMAGE_MAX_WIDTH=60, AD_IMAGE_MAX_HEIGHT=60)
    def test_reject_oversized_dimensions(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/ads/{self.ad.id}/images/"
        big = SimpleUploadedFile("big.jpg", make_image_bytes(w=300, h=300), content_type="image/jpeg")
        resp = self.client.post(url, data={"images": [big]}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Image too large", str(resp.data))

    @override_settings(AD_IMAGE_MAX_MB=0)  # any non-empty file will exceed 0 MB
    def test_reject_oversized_file(self):
        self.client.force_authenticate(self.owner)
        url = f"/api/ads/{self.ad.id}/images/"
        pic = SimpleUploadedFile("p.jpg", make_image_bytes(), content_type="image/jpeg")
        resp = self.client.post(url, data={"images": [pic]}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("File too large", str(resp.data))

    def test_replace_validates_and_checks_owner(self):
        self.client.force_authenticate(self.owner)
        upload_url = f"/api/ads/{self.ad.id}/images/"
        pic = SimpleUploadedFile("p.jpg", make_image_bytes(), content_type="image/jpeg")
        r = self.client.post(upload_url, data={"images": [pic]}, format="multipart")
        self.assertEqual(r.status_code, 201)
        img_id = r.data[0]["id"]

        # non-owner cannot replace
        self.client.force_authenticate(self.other)
        replace_url = f"/api/ad-images/{img_id}/replace/"
        new_pic = SimpleUploadedFile("n.jpg", make_image_bytes(), content_type="image/jpeg")
        r2 = self.client.post(replace_url, data={"image": new_pic}, format="multipart")
        self.assertEqual(r2.status_code, 403)

        # owner replaces with bad format -> 400
        self.client.force_authenticate(self.owner)
        bad = SimpleUploadedFile("bad.png", make_image_bytes(fmt="PNG"), content_type="image/png")
        with self.settings(AD_IMAGE_ALLOWED_FORMATS={"JPEG"}):
            r3 = self.client.post(replace_url, data={"image": bad}, format="multipart")
            self.assertEqual(r3.status_code, 400)
            self.assertIn("Unsupported format", str(r3.data))
