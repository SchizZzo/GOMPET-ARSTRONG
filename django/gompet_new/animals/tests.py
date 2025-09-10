from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from .models import Animal, AnimalParent, ParentRelation, Gender, Size, AnimalGallery
from ..users.models import (
    Organization,
    OrganizationMember,
    Address,
    OrganizationType,
)


class AnimalParentsFieldTest(APITestCase):
    """Ensure the animal endpoint exposes parent information."""

    def setUp(self):
        self.child = Animal.objects.create(
            name="Child",
            species="dog",
            gender=Gender.MALE,
            size=Size.SMALL,
        )
        self.mother = Animal.objects.create(
            name="Mother",
            species="dog",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )
        self.father = Animal.objects.create(
            name="Father",
            species="dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
        )
        AnimalParent.objects.create(
            animal=self.child,
            parent=self.mother,
            relation=ParentRelation.MOTHER,
        )
        AnimalParent.objects.create(
            animal=self.child,
            parent=self.father,
            relation=ParentRelation.FATHER,
        )

    def test_parents_field_present(self):
        url = f"/animals/animals/{self.child.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("parents", data)
        parent_names = {p["name"] for p in data["parents"]}
        self.assertSetEqual(parent_names, {"Mother", "Father"})


class AnimalGalleryCreateTest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com",
            password="password",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)

    def test_create_animal_with_gallery(self):
        image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        payload = {
            "name": "Doggie",
            "species": "dog",
            "gender": Gender.MALE,
            "size": Size.SMALL,
            "gallery": [
                {"image": f"data:image/png;base64,{image_data}"}
            ],
        }
        response = self.client.post("/animals/animals/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        animal_id = response.data["id"]
        self.assertEqual(AnimalGallery.objects.filter(animal_id=animal_id).count(), 1)


class AnimalGalleryMultipleUploadTest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user2@example.com",
            password="password",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)
        self.animal = Animal.objects.create(
            name="Multi",
            species="dog",
            gender=Gender.MALE,
            size=Size.SMALL,
        )

    def test_upload_multiple_images(self):
        image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        payload = {
            "animal": self.animal.id,
            "images": [
                f"data:image/png;base64,{image_data}",
                f"data:image/png;base64,{image_data}",
            ],
        }
        response = self.client.post("/animals/galleries/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            AnimalGallery.objects.filter(animal=self.animal).count(), 2
        )

    def test_upload_multiple_images_without_animal(self):
        """Uploading images without specifying the animal should fail."""
        image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        payload = {
            "images": [
                f"data:image/png;base64,{image_data}",
                f"data:image/png;base64,{image_data}",
            ]
        }
        response = self.client.post("/animals/galleries/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("animal", response.data)
        self.assertEqual(AnimalGallery.objects.count(), 0)


class AnimalCreateWithoutOptionalFieldsTest(APITestCase):
    """Ensure optional serializer fields can be omitted when creating."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="nogallery@example.com",
            password="password",
            first_name="No",
            last_name="Gallery",
        )
        self.client.force_authenticate(user=self.user)

    def test_create_without_gallery_and_characteristic_board(self):
        payload = {
            "name": "NoGallery",
            "species": "dog",
            "gender": Gender.MALE,
            "size": Size.SMALL,
        }
        response = self.client.post("/animals/animals/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        animal_id = response.data["id"]
        self.assertEqual(
            AnimalGallery.objects.filter(animal_id=animal_id).count(),
            0,
        )
        self.assertEqual(response.data["characteristicBoard"], [])


class AnimalGalleryUpdateReplaceTest(APITestCase):
    """Uploading new gallery images replaces the previous ones."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="galleryupdate@example.com",
            password="password",
            first_name="Gallery",
            last_name="Updater",
        )
        self.client.force_authenticate(user=self.user)
        self.image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        create_payload = {
            "name": "Initial",
            "species": "dog",
            "gender": Gender.MALE,
            "size": Size.SMALL,
            "gallery": [
                {"image": f"data:image/png;base64,{self.image_data}"}
            ],
        }
        response = self.client.post("/animals/animals/", create_payload, format="json")
        self.animal_id = response.data["id"]

    def test_update_replaces_gallery(self):
        update_payload = {
            "gallery": [
                {"image": f"data:image/png;base64,{self.image_data}"},
                {"image": f"data:image/png;base64,{self.image_data}"},
            ]
        }
        url = f"/animals/animals/{self.animal_id}/"
        response = self.client.patch(url, update_payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AnimalGallery.objects.filter(animal_id=self.animal_id).count(),
            2,
        )


class AnimalOrganizationFieldTest(APITestCase):
    """Ensure organization info is returned for animals with memberships."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="member@example.com",
            password="password",
            first_name="Member",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Test Org",
            email="org@example.com",
        )
        Address.objects.create(
            organization=self.organization,
            city="City",
            street="Street",
            house_number="1",
            zip_code="00-000",
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.animal = Animal.objects.create(
            name="OrgDog",
            species="dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
        )

    def test_organization_field_present(self):
        url = f"/animals/animals/{self.animal.id}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        org_data = response.data.get("organization")
        self.assertIsNotNone(org_data)
        self.assertEqual(org_data["id"], self.organization.id)
        self.assertEqual(org_data["address"]["city"], "City")
