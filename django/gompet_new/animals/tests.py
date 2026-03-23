from datetime import timedelta

import base64
import tempfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.gis.geos import Point
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import Address, MemberRole, Organization, OrganizationMember, OrganizationType, Species

from .models import (
    Animal,
    AnimalsBreedGroups,
    AnimalGallery,
    AnimalParent,
    Characteristics,
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


class AnimalSerializerLabelRepresentationTests(TestCase):
    """Ensure API representation exposes labels for species and breed."""

    def setUp(self):
        self.client = APIClient()
        self.species, _ = Species.objects.get_or_create(name="Dog")
        self.breed_group = AnimalsBreedGroups.objects.create(
            group_name="labrador retriever",
            species=self.species,
        )

    def test_serializer_maps_species_and_breed_ids_to_labels(self):
        animal = Animal.objects.create(
            name="LabelDog",
            species=str(self.species.id),
            breed=str(self.breed_group.id),
            gender=Gender.MALE,
            size=Size.SMALL,
        )

        data = AnimalSerializer(animal).data

        self.assertEqual(data["species"]["id"], self.species.id)
        self.assertEqual(data["species"]["label"], self.species.label)
        self.assertEqual(data["breed"]["id"], self.breed_group.id)
        self.assertEqual(data["breed"]["label"], self.breed_group.label)

    def test_animals_list_returns_species_and_breed_labels(self):
        animal = Animal.objects.create(
            name="ApiDog",
            species=str(self.species.id),
            breed=str(self.breed_group.id),
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )

        response = self.client.get(reverse("animal-list"))

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        payload = next(item for item in results if item["id"] == animal.id)

        self.assertEqual(payload["species"]["id"], self.species.id)
        self.assertEqual(payload["species"]["label"], self.species.label)
        self.assertEqual(payload["breed"]["id"], self.breed_group.id)
        self.assertEqual(payload["breed"]["label"], self.breed_group.label)


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

    def test_parent_and_child_must_have_same_species(self):
        cat_parent = Animal.objects.create(
            name="CatMom",
            species="  Cat  ",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )
        with self.assertRaises(ValidationError):
            AnimalParent.objects.create(
                animal=self.child,
                parent=cat_parent,
                relation=ParentRelation.MOTHER,
            )

    def test_parent_and_child_same_species_ignores_case_and_spaces(self):
        self.child.species = "  dog "
        self.child.save()
        spaced_mother = Animal.objects.create(
            name="SpacedMom",
            species="DOG",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
        )
        relation = AnimalParent.objects.create(
            animal=self.child,
            parent=spaced_mother,
            relation=ParentRelation.MOTHER,
        )
        self.assertEqual(relation.parent, spaced_mother)


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
        animal_image = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        img1 = SimpleUploadedFile("a.gif", image_bytes, content_type="image/gif")
        img2 = SimpleUploadedFile("b.gif", image_bytes, content_type="image/gif")
        data = {
            "name": "Multi",
            "image": animal_image,
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
        animal_image = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        img_str1 = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        img_str2 = "data:image/gif;base64," + base64.b64encode(image_bytes).decode()
        data = {
            "name": "Base64",
            "image": animal_image,
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

    def test_requires_main_image_when_creating_animal(self):
        data = {
            "name": "NoMainImage",
            "species": "Cat",
            "gender": Gender.FEMALE,
            "size": Size.SMALL,
        }

        serializer = AnimalSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("image", serializer.errors)


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
            city="TargetCity",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(1, 1),
        )
        Animal.objects.create(
            name="Other",
            species="Dog",
            city="OtherCity",
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
            city="NearCity",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(0.01, 0.01),
        )
        far = Animal.objects.create(
            name="Far",
            species="Dog",
            city="FarCity",
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

    def test_filter_animals_by_range_with_location_param(self):
        """Range filtering uses provided location when supplied."""
        near = Animal.objects.create(
            name="NearLoc",
            species="Dog",
            city="NearLocCity",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(1.01, 1.01),
        )
        far = Animal.objects.create(
            name="FarLoc",
            species="Dog",
            city="FarLocCity",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(2, 2),
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url, {"location": "POINT(1 1)", "range": 2000})
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data]
        self.assertIn(near.id, ids)
        self.assertNotIn(far.id, ids)


class AnimalFilteringRegressionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="filter-regression@example.com",
            password="testpass",
            first_name="Filter",
            last_name="Regression",
            location=Point(21.0, 52.0),
        )
        Animal.objects.create(
            name="FilterDog",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.user,
            location=Point(21.001, 52.001),
        )

    def test_filtering_range_does_not_raise_server_error(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("animalfiltering-list"), {"range": 5000})

        self.assertEqual(response.status_code, 200)


class AnimalAssignmentOptionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="member@example.com",
            password="testpass",
            first_name="Member",
            last_name="User",
        )
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com",
            password="testpass",
            first_name="Org",
            last_name="Owner",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Test Shelter",
            email="shelter@example.com",
            user=self.owner,
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.url = reverse("animal-assignment-options")

    def test_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_self_and_member_organizations(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)

        self_option = response.data["results"][0]
        org_option = response.data["results"][1]

        self.assertEqual(self_option["kind"], "self")
        self.assertEqual(self_option["owner_id"], self.user.id)
        self.assertIsNone(self_option["organization_id"])

        self.assertEqual(org_option["kind"], "organization")
        self.assertEqual(org_option["organization_id"], self.organization.id)
        self.assertEqual(org_option["owner_id"], self.organization.user_id)

    def test_excludes_organizations_without_add_animal_permission(self):
        readonly_owner = get_user_model().objects.create_user(
            email="owner-viewer@example.com",
            password="testpass",
            first_name="Viewer",
            last_name="Owner",
        )
        readonly_organization = Organization.objects.create(
            type=OrganizationType.FUND,
            name="Readonly Org",
            email="readonly@example.com",
            user=readonly_owner,
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=readonly_organization,
            role=MemberRole.VIEWER,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        organization_ids = {
            option["organization_id"]
            for option in response.data["results"]
            if option["kind"] == "organization"
        }
        self.assertIn(self.organization.id, organization_ids)
        self.assertNotIn(readonly_organization.id, organization_ids)


class AnimalErrorResponseFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="errors-user@example.com",
            password="testpass",
            first_name="Errors",
            last_name="User",
        )
        self.owner = get_user_model().objects.create_user(
            email="errors-owner@example.com",
            password="testpass",
            first_name="Errors",
            last_name="Owner",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Errors Shelter",
            email="errors-shelter@example.com",
            user=self.owner,
        )

    def test_401_error_payload_format(self):
        response = self.client.get(reverse("animal-assignment-options"))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.data,
            {
                "status": 401,
                "code": "not_authenticated",
                "message": "Authentication credentials were not provided.",
                "errors": {},
            },
        )

    def test_403_error_payload_format(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("animal-list"),
            {"organization": self.organization.id},
            format="json",
        )

        self.assertIn(response.status_code, (400, 403))
        self.assertEqual(
            response.data,
            {
                "status": 403,
                "code": "permission_denied",
                "message": "You do not have permission to perform this action.",
                "errors": {},
            },
        )

    def test_404_error_payload_format(self):
        response = self.client.get(reverse("animal-detail", args=[999999]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data,
            {
                "status": 404,
                "code": "not_found",
                "message": "Resource not found.",
                "errors": {},
            },
        )

    def test_400_validation_error_payload_format(self):
        self.user.user_permissions.add(Permission.objects.get(codename="add_animal"))
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("animal-list"),
            {
                "name": "NoMainImage",
                "species": "Dog",
                "gender": Gender.FEMALE,
                "size": Size.SMALL,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertEqual(
            response.data["errors"],
            {"image": ["This field is required."]},
        )

    def test_500_error_payload_format(self):
        with patch("animals.api_views.AnimalViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get(reverse("animal-list"))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data,
            {
                "status": 500,
                "code": "server_error",
                "message": "An internal server error occurred.",
                "errors": {},
            },
        )


class AnimalPartialUpdateOrganizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="member-update@example.com",
            password="testpass",
            first_name="Member",
            last_name="Updater",
        )
        self.owner = get_user_model().objects.create_user(
            email="owner-update@example.com",
            password="testpass",
            first_name="Org",
            last_name="Owner",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Update Shelter",
            email="update-shelter@example.com",
            user=self.owner,
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=self.organization,
        )
        self.animal = Animal.objects.create(
            name="Patchable",
            species="Dog",
            gender=Gender.FEMALE,
            size=Size.SMALL,
            owner=self.owner,
            organization=self.organization,
        )
        self.url = reverse("animal-detail", args=[self.animal.id])

    def test_patch_accepts_string_null_for_organization_id(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {"organization_id": "null"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNone(self.animal.organization)

    def test_patch_accepts_null_for_organization_field(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {"organization": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNone(self.animal.organization)

    def test_patch_organization_null_takes_precedence_over_stale_organization_id(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                "organization": None,
                "organization_id": self.organization.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNone(self.animal.organization)

    def test_patch_clears_organization_in_response_payload(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {"organization": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["organization"])

    def test_patch_organization_null_sets_location_from_animal_owner(self):
        self.client.force_authenticate(user=self.user)
        owner_location = Point(20.0, 52.0)
        self.owner.location = owner_location
        self.owner.save(update_fields=["location"])
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        response = self.client.patch(
            self.url,
            {"organization": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertIsNotNone(self.animal.location)
        self.assertAlmostEqual(self.animal.location.x, owner_location.x, places=6)
        self.assertAlmostEqual(self.animal.location.y, owner_location.y, places=6)

    def test_patch_changing_organization_sets_location_from_organization_address(self):
        self.client.force_authenticate(user=self.user)
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        new_owner = get_user_model().objects.create_user(
            email="owner-location@example.com",
            password="testpass",
            first_name="Org",
            last_name="Location",
        )
        new_organization = Organization.objects.create(
            type=OrganizationType.FUND,
            name="Location Foundation",
            email="location-foundation@example.com",
            user=new_owner,
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=new_organization,
        )
        address_location = Point(19.94, 50.06)
        Address.objects.create(
            organization=new_organization,
            city="Krakow",
            street="Dluga",
            house_number="10",
            zip_code="30-001",
            location=address_location,
        )

        response = self.client.patch(
            self.url,
            {"organization": new_organization.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.organization, new_organization)
        self.assertIsNotNone(self.animal.location)
        self.assertAlmostEqual(self.animal.location.x, address_location.x, places=6)
        self.assertAlmostEqual(self.animal.location.y, address_location.y, places=6)

    def test_patch_changing_organization_without_address_location_clears_animal_location(self):
        self.client.force_authenticate(user=self.user)
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        no_address_owner = get_user_model().objects.create_user(
            email="owner-no-address@example.com",
            password="testpass",
            first_name="Org",
            last_name="NoAddress",
        )
        no_address_organization = Organization.objects.create(
            type=OrganizationType.OTHER,
            name="No Address Org",
            email="no-address-org@example.com",
            user=no_address_owner,
        )
        OrganizationMember.objects.create(
            user=self.user,
            organization=no_address_organization,
        )

        response = self.client.patch(
            self.url,
            {"organization": no_address_organization.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.organization, no_address_organization)
        self.assertIsNone(self.animal.location)

    def test_patch_location_without_city_recomputes_city_from_location(self):
        self.client.force_authenticate(user=self.user)
        self.animal.city = "OldCity"
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["city", "location"])

        with patch("animals.models.Animal.get_city", return_value="NewCity"):
            response = self.client.patch(
                self.url,
                {"location": "POINT(19.94 50.06)"},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.city, "NewCity")

    def test_patch_organization_null_without_city_uses_owner_location_for_city(self):
        self.client.force_authenticate(user=self.user)
        self.owner.location = Point(20.0, 52.0)
        self.owner.save(update_fields=["location"])
        self.animal.city = "OldCity"
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["city", "location"])

        with patch("animals.models.Animal.get_city", return_value="OwnerCity"):
            response = self.client.patch(
                self.url,
                {"organization": None},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.city, "OwnerCity")

    def test_patch_owner_change_is_forbidden_for_non_superuser(self):
        self.client.force_authenticate(user=self.user)
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        new_owner_location = Point(14.55, 53.43)
        new_owner = get_user_model().objects.create_user(
            email="owner-new-location@example.com",
            password="testpass",
            first_name="Owner",
            last_name="NewLocation",
            location=new_owner_location,
        )

        with patch("animals.models.Animal.get_city", return_value="Szczecin"):
            response = self.client.patch(
                self.url,
                {"owner": new_owner.id},
                format="json",
            )

        self.assertIn(response.status_code, (400, 403))
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.owner, self.owner)
        self.assertIsNotNone(self.animal.location)
        self.assertAlmostEqual(self.animal.location.x, 17.0, places=6)
        self.assertAlmostEqual(self.animal.location.y, 51.0, places=6)

    def test_patch_owner_change_without_location_is_forbidden_for_non_superuser(self):
        self.client.force_authenticate(user=self.user)
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        new_owner_without_location = get_user_model().objects.create_user(
            email="owner-without-location@example.com",
            password="testpass",
            first_name="Owner",
            last_name="NoLocation",
        )

        response = self.client.patch(
            self.url,
            {"owner": new_owner_without_location.id},
            format="json",
        )

        self.assertIn(response.status_code, (400, 403))
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.owner, self.owner)
        self.assertIsNotNone(self.animal.location)
        self.assertAlmostEqual(self.animal.location.x, 17.0, places=6)
        self.assertAlmostEqual(self.animal.location.y, 51.0, places=6)

    def test_superuser_can_change_owner_and_sync_location(self):
        admin_user = get_user_model().objects.create_superuser(
            email="animals-admin@example.com",
            password="testpass",
            first_name="Animals",
            last_name="Admin",
        )
        self.client.force_authenticate(user=admin_user)
        self.animal.location = Point(17.0, 51.0)
        self.animal.save(update_fields=["location"])

        new_owner_location = Point(14.55, 53.43)
        new_owner = get_user_model().objects.create_user(
            email="owner-superuser-update@example.com",
            password="testpass",
            first_name="Owner",
            last_name="SuperuserUpdate",
            location=new_owner_location,
        )

        response = self.client.patch(
            self.url,
            {"owner": new_owner.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.animal.refresh_from_db()
        self.assertEqual(self.animal.owner, new_owner)
        self.assertIsNotNone(self.animal.location)
        self.assertAlmostEqual(self.animal.location.x, new_owner_location.x, places=6)
        self.assertAlmostEqual(self.animal.location.y, new_owner_location.y, places=6)


class AnimalsBreedGroupsEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.species, _ = Species.objects.get_or_create(name="Dog")

    def test_list_returns_uppercase_label_for_breed_group(self):
        breed_group = AnimalsBreedGroups.objects.create(
            group_name="labrador retriever",
            species=self.species,
            description="Friendly family dog",
        )
        breed_group.refresh_from_db()

        response = self.client.get("/animals/animal-breed/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        payload = next(item for item in results if item["id"] == breed_group.id)
        self.assertEqual(breed_group.label, "LABRADOR_RETRIEVER")
        self.assertEqual(payload["label"], breed_group.label)
        self.assertEqual(payload["group_name"], "labrador retriever")

    def test_list_returns_english_label_for_polish_breed_group_name(self):
        breed_group = AnimalsBreedGroups.objects.create(
            group_name="Polski owczarek nizinny",
            species=self.species,
            description="Polish breed",
        )
        breed_group.refresh_from_db()

        response = self.client.get("/animals/animal-breed/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        payload = next(item for item in results if item["id"] == breed_group.id)
        self.assertEqual(breed_group.label, "POLISH_SHEPHERD_LOWLAND")
        self.assertEqual(payload["label"], breed_group.label)


class AnimalCharacteristicsListEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_returns_dog_characteristics_with_name_uppercase_label_and_species(self):
        response = self.client.get("/animals/characteristics/")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(len(response.data) >= 20)
        db_names = set(Characteristics.objects.values_list("characteristic", flat=True))
        api_names = {item["name"] for item in response.data}
        self.assertEqual(api_names, db_names)
        self.assertFalse(Characteristics.objects.filter(label="").exists())

        has_chip = next((item for item in response.data if item["name"] == "hasChip"), None)
        city = next((item for item in response.data if item["name"] == "canLiveInACity"), None)
        has_chip_db = Characteristics.objects.get(characteristic="hasChip")
        city_db = Characteristics.objects.get(characteristic="canLiveInACity")
        dog_species = Species.objects.get(label="DOG")

        self.assertIsNotNone(has_chip)
        self.assertEqual(has_chip["id"], has_chip_db.id)
        self.assertEqual(has_chip["label"], has_chip_db.label)
        self.assertEqual(has_chip["species"], dog_species.label)
        self.assertIsNotNone(city)
        self.assertEqual(city["id"], city_db.id)
        self.assertEqual(city["label"], city_db.label)
        self.assertEqual(city["species"], dog_species.label)

        for item in response.data:
            self.assertIsInstance(item["id"], int)
            self.assertEqual(set(item.keys()), {"id", "name", "label", "species"})

    def test_filters_characteristics_by_species_query_param(self):
        cat_species = Species.objects.create(name="Cat")
        cat_characteristic = Characteristics.objects.create(
            characteristic="usesLitterBox",
            species=cat_species,
        )

        response = self.client.get("/animals/characteristics/?species=CAT")

        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.data}
        self.assertIn(cat_characteristic.characteristic, names)
        self.assertNotIn("hasChip", names)
        self.assertTrue(all(item["species"] == cat_species.label for item in response.data))
