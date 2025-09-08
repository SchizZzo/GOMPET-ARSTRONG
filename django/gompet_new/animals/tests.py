from rest_framework.test import APITestCase

from .models import Animal, AnimalParent, ParentRelation, Gender, Size


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
