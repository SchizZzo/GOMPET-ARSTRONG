from datetime import timedelta

import base64
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    Animal,
    AnimalGallery,
    AnimalParent,
    Gender,
    ParentRelation,
    Size,
)
from .serializers import AnimalSerializer


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

