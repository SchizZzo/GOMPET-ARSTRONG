from datetime import timedelta

import base64
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APIClient

from .models import (
    Animal,
    AnimalGallery,
    AnimalParent,
    Gender,
    ParentRelation,
    Size,
)
from .serializers import AnimalSerializer, AnimalParentSerializer


class AnimalModelTests(TestCase):
    """Tests for core Animal model helpers."""

    def test_age_property_calculates_years(self):
        birth_date = timezone.now().date() - timedelta(days=5 * 365)
        animal = Animal.objects.create(
            name="Rex",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            birth_date=birth_date,
        )
        self.assertEqual(animal.age, 5)

    def test_age_property_returns_none_without_birth_date(self):
        animal = Animal.objects.create(
            name="Mia",
            species="Cat",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )
        self.assertIsNone(animal.age)

    def test_soft_delete_sets_deleted_at(self):
        animal = Animal.objects.create(
            name="Bolt",
            species="Dog",
            gender=Gender.MALE,
            size=Size.LARGE,
        )
        self.assertIsNone(animal.deleted_at)
        animal.soft_delete()
        animal.refresh_from_db()
        self.assertIsNotNone(animal.deleted_at)


class AnimalSerializerAgeTests(TestCase):
    """Tests for age field serialization."""

    def test_serializer_returns_computed_age(self):
        birth_date = timezone.now().date() - timedelta(days=3 * 365)
        animal = Animal.objects.create(
            name="Toby",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            birth_date=birth_date,
        )
        data = AnimalSerializer(animal).data
        self.assertEqual(data["age"], 3)


class AnimalParentModelTests(TestCase):
    """Validations for AnimalParent relations."""

    def setUp(self):
        self.child = Animal.objects.create(
            name="Junior",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
        )
        self.mother = Animal.objects.create(
            name="Mom",
            species="Dog",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )
        self.father = Animal.objects.create(
            name="Dad",
            species="Dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
        )
        self.other = Animal.objects.create(
            name="Other",
            species="Dog",
            gender=Gender.OTHER,
            size=Size.MEDIUM,
        )

    def test_unique_relation_per_parent(self):
        AnimalParent.objects.create(
            animal=self.child,
            parent=self.mother,
            relation=ParentRelation.MOTHER,
        )
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=self.other,
                relation=ParentRelation.MOTHER,
            )

    def test_max_two_parents(self):
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
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=self.other,
                relation=ParentRelation.MOTHER,
            )

    def test_relation_matches_parent_gender(self):
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=self.mother,
                relation=ParentRelation.FATHER,
            )
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=self.father,
                relation=ParentRelation.MOTHER,
            )

    def test_parent_must_be_older_than_child(self):
        self.child.birth_date = timezone.now().date()
        self.child.save()
        self.mother.birth_date = self.child.birth_date + timedelta(days=1)
        self.mother.save()
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=self.mother,
                relation=ParentRelation.MOTHER,
            )


class AnimalParentSerializerTests(TestCase):
    """Tests for AnimalParentSerializer validation and saving."""

    def setUp(self):
        self.child = Animal.objects.create(
            name="Junior",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
        )
        self.mother = Animal.objects.create(
            name="Mom",
            species="Dog",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )

    def test_serializer_creates_relation_with_both_ids(self):
        data = {
            "animal": self.child.id,
            "parent": self.mother.id,
            "relation": ParentRelation.MOTHER,
        }
        serializer = AnimalParentSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        relation = serializer.save()
        self.assertEqual(relation.animal, self.child)
        self.assertEqual(relation.parent, self.mother)


class AnimalGalleryModelTests(TestCase):
    """Basic tests for AnimalGallery model."""

    def setUp(self):
        self.animal = Animal.objects.create(
            name="Picasso",
            species="Cat",
            gender=Gender.MALE,
            size=Size.SMALL,
        )

        # minimal valid GIF byte content
        self.image_data = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_creates_gallery_item_for_animal(self):
        image = SimpleUploadedFile(
            "test.gif", self.image_data, content_type="image/gif"
        )
        gallery = AnimalGallery.objects.create(animal=self.animal, image=image)
        self.assertEqual(gallery.animal, self.animal)
        self.assertTrue(gallery.image.name.startswith("animals/gallery/"))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_gallery_items_deleted_with_animal(self):
        image = SimpleUploadedFile(
            "test.gif", self.image_data, content_type="image/gif"
        )
        gallery = AnimalGallery.objects.create(animal=self.animal, image=image)
        self.animal.delete()
        self.assertFalse(
            AnimalGallery.objects.filter(pk=gallery.pk).exists()
        )


class AnimalSerializerGalleryTests(TestCase):
    """Ensure serializer handles multiple gallery uploads."""

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_create_animal_with_multiple_gallery_images(self):
        image_bytes = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        img1 = SimpleUploadedFile("a.gif", image_bytes, content_type="image/gif")
        img2 = SimpleUploadedFile("b.gif", image_bytes, content_type="image/gif")
        data = {
            "name": "Multi",
            "species": "Cat",
            "gender": Gender.FEMALE,
            "size": Size.SMALL,
            "gallery": [{"image": img1}, {"image": img2}],
        }
        serializer = AnimalSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        animal = serializer.save()
        self.assertEqual(animal.gallery.count(), 2)
        for item in animal.gallery.all():
            self.assertTrue(item.image.name.startswith("animals/gallery/"))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_accepts_base64_encoded_gallery_image(self):
        image_bytes = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\n\x00\x01\x00,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        img_str1 = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        img_str2 = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        data = {
            "name": "Base64",
            "species": "Cat",
            "gender": Gender.FEMALE,
            "size": Size.SMALL,
            "gallery": [{"image": img_str1}, {"image": img_str2}],
        }
        serializer = AnimalSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        animal = serializer.save()
        self.assertEqual(animal.gallery.count(), 2)

    def test_requires_image_for_each_gallery_item(self):
        """Serializer should error if gallery entries lack images."""

        data = {
            "name": "NoPics",
            "species": "Cat",
            "gender": Gender.FEMALE,
            "size": Size.SMALL,
            "gallery": [{}, {}],
        }
        serializer = AnimalSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        errors = serializer.errors.get("gallery")
        self.assertEqual(len(errors), 2)
        for err in errors:
            self.assertIn("image", err)


class AnimalViewSetGeoFilteringTests(TestCase):
    """Tests for location and range filtering in AnimalViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="geo@example.com",
            password="testpass",
            first_name="Geo",
            last_name="User",
            location=Point(0, 0),
        )
        self.list_url = reverse("animal-list")

    def test_filter_animals_by_location(self):
        """Only animals matching the provided location should be returned."""
        target = Animal.objects.create(
            name="Target",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(1, 1),
        )
        Animal.objects.create(
            name="Other",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(2, 2),
        )

        response = self.client.get(self.list_url, {"location": "POINT(1 1)"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], [target.id])

    def test_filter_animals_by_range(self):
        """Animals outside the given range from user location are excluded."""
        near = Animal.objects.create(
            name="Near",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(0.01, 0.01),
        )
        far = Animal.objects.create(
            name="Far",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(2, 2),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url, {"range": 2000})
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data]
        self.assertIn(near.id, ids)
        self.assertNotIn(far.id, ids)

