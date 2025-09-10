from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from .models import Animal, AnimalParent, ParentRelation, Gender, Size, AnimalGallery


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


class AnimalGalleryUpdateTest(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com",
            password="password",
            first_name="Test",
            last_name="User",
        )
        self.client.force_authenticate(user=self.user)
        self.animal = Animal.objects.create(
            name="Doggie",
            species="dog",
            gender=Gender.MALE,
            size=Size.SMALL,
        )
        self.gallery_item = AnimalGallery.objects.create(
            animal=self.animal,
            image="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )

    def test_update_animal_gallery(self):
        new_image_data = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
        )
        payload = {
            "name": "Doggie Updated",
            "species": "dog",
            "gender": Gender.MALE.value,
            "size": Size.SMALL.value,
            "gallery": [
                {"image": f"data:image/png;base64,{new_image_data}"}
            ],
        }
        response = self.client.put(f"/animals/animals/{self.animal.id}/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.name, "Doggie Updated")
        # gallery should be replaced with the new list (one item)
        self.assertEqual(AnimalGallery.objects.filter(animal=self.animal).count(), 1)

