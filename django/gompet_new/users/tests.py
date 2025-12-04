import shutil
import tempfile

from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework.reverse import reverse
from rest_framework.test import APIClient

from .models import Address, Organization, User


TEST_IMAGE_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/xcAAn8B9p7mDK0AAAAASUVORK5CYII="
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class OrganizationImageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="password123",
            first_name="Org",
            last_name="Owner",
        )
        self.client.force_authenticate(self.user)

    def tearDown(self):
        # Clean uploaded files between tests
        shutil.rmtree(default_storage.location, ignore_errors=True)

    def _base_payload(self):
        return {
            "type": "SHELTER",
            "name": "Test Org",
            "email": "test@example.com",
            "phone": "+48123123123",
            "description": {},
            "address": {
                "city": "City",
                "street": "Street",
                "house_number": "1",
                "zip_code": "00-000",
                "lat": None,
                "lng": None,
                "location": None,
                "species": [],
            },
        }

    def test_create_organization_with_base64_image(self):
        url = reverse("organization-list")
        payload = self._base_payload()
        payload["image"] = f"data:image/png;base64,{TEST_IMAGE_BASE64}"

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        org = Organization.objects.get(pk=response.data["id"])
        self.assertTrue(org.image.name.endswith(".png"))
        self.assertTrue(default_storage.exists(org.image.name))

    def test_update_organization_with_base64_image(self):
        # Create initial organization without an image
        org = Organization.objects.create(
            type="SHELTER",
            name="Initial Org",
            email="initial@example.com",
            phone="+48123123123",
            description={},
            user=self.user,
        )
        Address.objects.create(
            organization=org,
            city="City",
            street="Street",
            house_number="1",
            zip_code="00-000",
            lat=None,
            lng=None,
        )
        update_url = reverse("organization-detail", args=[org.id])

        payload = {
            "image": TEST_IMAGE_BASE64,
        }

        response = self.client.patch(update_url, payload, format="json")

        self.assertEqual(response.status_code, 200)
        org.refresh_from_db()
        self.assertTrue(org.image.name.endswith(".png"))
        self.assertTrue(default_storage.exists(org.image.name))
