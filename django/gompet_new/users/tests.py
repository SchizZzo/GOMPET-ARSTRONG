from __future__ import annotations
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework import serializers, status
from rest_framework.test import APIClient

from common.models import Notification

from .models import (
    Address,
    BreedingType,
    BreedingTypeOrganizations,
    MemberRole,
    Organization,
    OrganizationType,
    OrganizationMember,
    Species,
)
from .serializers import (
    Base64ImageField,
    OrganizationCreateSerializer,
    OrganizationUpdateSerializer,
    UserUpdateSerializer,
)
from .services import CannotDeleteUser, delete_user_account

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, "Użytkownik musi mieć adres e-mail"):
            User.objects.create_user(email="", password="secret")

    def test_create_user_sets_defaults(self):
        user = User.objects.create_user(
            email="Test@Example.com",
            password="secret",
            first_name="John",
            last_name="Doe",
        )

        self.assertEqual(user.email, "Test@example.com")
        self.assertTrue(user.check_password("secret"))
        self.assertEqual(user.role, user._meta.get_field("role").default)

    def test_create_superuser_has_admin_flags(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass",
            first_name="Admin",
            last_name="User",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertEqual(user.role, user._meta.get_field("role").choices[0][0])

    def test_create_user_with_image(self):
        user = User.objects.create_user(
            email="image@example.com",
            password="secret",
            first_name="Image",
            last_name="User",
            image="https://example.com/avatar.png",
        )

        self.assertEqual(user.image, "https://example.com/avatar.png")


class UserModelTests(TestCase):
    def test_full_name_property(self):
        user = User.objects.create_user(
            email="jane@example.com",
            password="secret",
            first_name="Jane",
            last_name="Doe",
        )

        self.assertEqual(user.full_name, "Jane Doe")

    def test_soft_delete_marks_user_inactive(self):
        user = User.objects.create_user(
            email="soft@example.com",
            password="secret",
            first_name="Soft",
            last_name="Delete",
        )

        user.soft_delete()
        user.refresh_from_db()

        self.assertFalse(user.is_active)
        self.assertTrue(user.is_deleted)
        self.assertIsNotNone(user.deleted_at)


class DeleteUserAccountTests(TestCase):
    def _create_organization_with_owner(self, owner: User):
        org = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name=f"Shelter {owner.id}",
            email=f"shelter-{owner.id}@example.com",
            image="",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=org,
            role=MemberRole.OWNER,
        )
        return org

    def test_cannot_delete_only_owner(self):
        owner = User.objects.create_user(
            email="owner@example.com",
            password="secret",
            first_name="Only",
            last_name="Owner",
        )
        self._create_organization_with_owner(owner)

        with self.assertRaises(CannotDeleteUser):
            delete_user_account(owner)

    def test_delete_user_account_anonymizes_and_removes_sessions(self):
        owner = User.objects.create_user(
            email="owner2@example.com",
            password="secret",
            first_name="Primary",
            last_name="Owner",
        )
        other_owner = User.objects.create_user(
            email="coowner@example.com",
            password="secret",
            first_name="Co",
            last_name="Owner",
        )
        org = self._create_organization_with_owner(owner)
        OrganizationMember.objects.create(
            user=other_owner,
            organization=org,
            role=MemberRole.OWNER,
        )

        session = SessionStore()
        session["_auth_user_id"] = str(owner.id)
        session.create()

        with mock.patch("users.services.util.find_spec", return_value=None):
            delete_user_account(owner)

        owner.refresh_from_db()
        self.assertTrue(owner.email.startswith(f"deleted_{owner.id}@example.invalid"))
        self.assertEqual(owner.first_name, "")
        self.assertEqual(owner.last_name, "")
        self.assertEqual(owner.phone, "")
        self.assertEqual(owner.image, "")
        self.assertIsNone(owner.location)
        self.assertFalse(owner.is_active)
        self.assertTrue(owner.is_deleted)
        self.assertIsNotNone(owner.deleted_at)
        self.assertTrue(owner.memberships.exists())
        self.assertTrue(owner.organizations.exists())
        self.assertFalse(
            Session.objects.filter(session_key=session.session_key).exists()
        )


class OrganizationMemberNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_invite_sends_notification_to_owner(self):
        owner = User.objects.create_user(
            email="owner-invite@example.com",
            password="secret",
            first_name="Owner",
            last_name="Invite",
        )
        org = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Invite Shelter",
            email="invite-shelter@example.com",
            image="",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=org,
            role=MemberRole.OWNER,
        )
        inviter = User.objects.create_user(
            email="inviter@example.com",
            password="secret",
            first_name="Inviter",
            last_name="User",
        )
        invited = User.objects.create_user(
            email="invitee@example.com",
            password="secret",
            first_name="Invitee",
            last_name="User",
        )
        self.client.force_authenticate(user=inviter)

        response = self.client.post(
            "/users/organization-members/",
            {"user": invited.id, "organization": org.id, "role": MemberRole.STAFF},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = Notification.objects.get(recipient=owner)
        self.assertEqual(notification.actor, inviter)
        self.assertEqual(notification.verb, "wysłał(a) zaproszenie do organizacji")
        self.assertEqual(notification.target_type, "organization")
        self.assertEqual(notification.target_id, org.id)


class UserUpdateCurrentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_put_requires_authentication(self):
        response = self.client.put(
            "/users/users/",
            {"first_name": "New"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_put_updates_current_user(self):
        user = User.objects.create_user(
            email="edit@example.com",
            password="secret",
            first_name="Old",
            last_name="Name",
        )
        self.client.force_authenticate(user=user)

        payload = {
            "first_name": "Updated",
            "last_name": "User",
            "email": user.email,
            "phone": "",
            "role": user.role,
            "location": None,
            "is_active": True,
            "is_staff": False,
        }

        response = self.client.put("/users/users/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Updated")
        self.assertEqual(user.last_name, "User")

    def test_patch_partially_updates_current_user(self):
        user = User.objects.create_user(
            email="patch@example.com",
            password="secret",
            first_name="Before",
            last_name="Name",
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            "/users/users/",
            {"first_name": "After"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "After")
        self.assertEqual(user.last_name, "Name")


User = get_user_model()


PNG_DATA_URI = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)
PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


class DummySerializer(serializers.Serializer):
    image = Base64ImageField(required=True, allow_null=False)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class Base64ImageFieldTests(TestCase):
    def test_accepts_data_uri(self) -> None:
        ser = DummySerializer(data={"image": PNG_DATA_URI})
        self.assertTrue(ser.is_valid(), ser.errors)
        img = ser.validated_data["image"]
        self.assertTrue(hasattr(img, "name"))
        self.assertTrue(img.name.endswith(".png"))

    def test_accepts_plain_base64(self) -> None:
        ser = DummySerializer(data={"image": PNG_BASE64})
        self.assertTrue(ser.is_valid(), ser.errors)
        img = ser.validated_data["image"]
        self.assertTrue(hasattr(img, "name"))
        self.assertTrue(img.name.endswith(".png"))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class UserUpdateSerializerImageTests(TestCase):
    def test_updates_user_image_from_base64_data_uri(self) -> None:
        user = User.objects.create_user(
            email="img@example.com",
            password="secret",
            first_name="Img",
            last_name="User",
        )

        ser = UserUpdateSerializer(
            instance=user,
            data={"image": PNG_DATA_URI},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        updated = ser.save()

        # Ensure file was assigned and saved
        self.assertTrue(updated.image)
        self.assertTrue(updated.image.name.endswith(".png"))
        self.assertTrue(default_storage.exists(updated.image.name))

        # Cleanup the file to avoid cluttering temp MEDIA_ROOT
        default_storage.delete(updated.image.name)

    def test_updates_user_image_from_plain_base64(self) -> None:
        user = User.objects.create_user(
            email="img2@example.com",
            password="secret",
            first_name="Img2",
            last_name="User",
        )

        ser = UserUpdateSerializer(
            instance=user,
            data={"image": PNG_BASE64},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        updated = ser.save()

        self.assertTrue(updated.image)
        self.assertTrue(updated.image.name.endswith(".png"))
        self.assertTrue(default_storage.exists(updated.image.name))

        default_storage.delete(updated.image.name)

    def test_accepts_null_image(self) -> None:
        user = User.objects.create_user(
            email="nullimg@example.com",
            password="secret",
            first_name="Null",
            last_name="Img",
        )

        ser = UserUpdateSerializer(
            instance=user,
            data={"image": None},
            partial=True,
        )
        self.assertTrue(ser.is_valid(), ser.errors)
        updated = ser.save()

        # When setting None, ensure image is cleared or remains falsy
        self.assertFalse(bool(updated.image))


class OrganizationSerializerValidationTests(TestCase):
    def setUp(self):
        self.base_address = {
            "city": "Warszawa",
            "street": "Testowa",
            "house_number": "10",
            "zip_code": "00-001",
        }
        self.base_payload = {
            "type": OrganizationType.SHELTER,
            "name": "Fundacja Zwierzak",
            "email": "kontakt@example.com",
            "phone": "+48123123123",
            "description": {},
            "address": self.base_address,
        }

    def test_create_requires_name(self):
        payload = dict(self.base_payload, name="")
        serializer = OrganizationCreateSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_create_requires_email_or_phone(self):
        payload = dict(self.base_payload, email="", phone="")
        serializer = OrganizationCreateSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_create_requires_full_address(self):
        address = dict(self.base_address)
        address.pop("street")
        payload = dict(self.base_payload, address=address)
        serializer = OrganizationCreateSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("address", serializer.errors)
        self.assertIn("street", serializer.errors["address"])

    def test_update_requires_name_and_contact(self):
        owner = User.objects.create_user(
            email="owner@example.com",
            password="secret",
            first_name="Owner",
            last_name="User",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Organizacja",
            email="org@example.com",
            phone="+48123123123",
            user=owner,
        )
        Address.objects.create(
            organization=organization,
            city="Poznań",
            street="Stara",
            house_number="5",
            zip_code="60-001",
        )

        serializer = OrganizationUpdateSerializer(
            instance=organization,
            data={"name": "", "email": "", "phone": ""},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)
        self.assertIn("email", serializer.errors)

    def test_update_requires_address_when_missing(self):
        owner = User.objects.create_user(
            email="owner2@example.com",
            password="secret",
            first_name="Owner",
            last_name="Two",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Organizacja 2",
            email="org2@example.com",
            phone="+48123123123",
            user=owner,
        )

        serializer = OrganizationUpdateSerializer(
            instance=organization,
            data={"address": {"city": "Lublin"}},
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("address", serializer.errors)
        self.assertIn("street", serializer.errors["address"])
        self.assertIn("house_number", serializer.errors["address"])


class OrganizationAddressViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_lists_addresses_with_organization_details(self):
        owner = User.objects.create_user(
            email="owner-address@example.com",
            password="secret",
            first_name="Owner",
            last_name="Address",
        )

        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Adresowa Organizacja",
            email="org-address@example.com",
            phone="",
            user=owner,
        )

        address = Address.objects.create(
            organization=organization,
            city="Warszawa",
            street="Testowa",
            house_number="10",
            zip_code="00-001",
        )

        response = self.client.get("/users/organization-addresses/")

        self.assertEqual(response.status_code, 200)

        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)

        payload = results[0]
        self.assertEqual(payload["organization_id"], organization.id)
        self.assertEqual(payload["organization_name"], organization.name)
        self.assertEqual(payload["city"], address.city)


class OrganizationFilteringViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _create_org_with_address(self, *, owner, name, org_type, location=None):
        organization = Organization.objects.create(
            type=org_type,
            name=name,
            email=f"{name.replace(' ', '').lower()}@example.com",
            phone="",
            user=owner,
        )
        address = Address.objects.create(
            organization=organization,
            city="Warszawa",
            street="Testowa",
            house_number="1",
            zip_code="00-001",
            location=location,
        )
        return organization, address

    def test_lists_organizations_with_and_without_range(self):
        user = User.objects.create_user(
            email="filter-range@example.com",
            password="secret",
            first_name="Range",
            last_name="User",
        )
        user.location = Point(21.0, 52.0)
        user.save(update_fields=["location"])
        self.client.force_authenticate(user=user)

        near_org, near_address = self._create_org_with_address(
            owner=user,
            name="Near Shelter",
            org_type=OrganizationType.SHELTER,
            location=Point(21.001, 52.001),
        )
        self._create_org_with_address(
            owner=user,
            name="Far Clinic",
            org_type=OrganizationType.CLINIC,
            location=Point(22.0, 52.0),
        )

        response = self.client.get("/users/organization-filtering/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], near_org.id)
        self.assertEqual(results[0]["address"]["city"], near_address.city)

        response = self.client.get("/users/organization-filtering/?range=1000")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Near Shelter")

    def test_filters_by_organization_type(self):
        owner = User.objects.create_user(
            email="filter-type@example.com",
            password="secret",
            first_name="Type",
            last_name="User",
        )
        self._create_org_with_address(
            owner=owner,
            name="Shelter Org",
            org_type=OrganizationType.SHELTER,
        )
        self._create_org_with_address(
            owner=owner,
            name="Clinic Org",
            org_type=OrganizationType.CLINIC,
        )

        response = self.client.get(
            "/users/organization-filtering/?organization-type=SHELTER"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], OrganizationType.SHELTER)

    def test_filters_by_species(self):
        owner = User.objects.create_user(
            email="filter-species@example.com",
            password="secret",
            first_name="Species",
            last_name="User",
        )
        dog = Species.objects.create(name="dog")
        cat = Species.objects.create(name="cat")
        dog_org, dog_address = self._create_org_with_address(
            owner=owner,
            name="Dog Shelter",
            org_type=OrganizationType.SHELTER,
        )
        cat_org, cat_address = self._create_org_with_address(
            owner=owner,
            name="Cat Clinic",
            org_type=OrganizationType.CLINIC,
        )
        dog_address.species.add(dog)
        cat_address.species.add(cat)

        response = self.client.get("/users/organization-filtering/?species=dog")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], dog_org.id)
        self.assertIn(dog.id, results[0]["address"]["species"])
        self.assertNotEqual(results[0]["id"], cat_org.id)

    def test_filters_by_breeding_type(self):
        owner = User.objects.create_user(
            email="filter-breeding@example.com",
            password="secret",
            first_name="Breeding",
            last_name="User",
        )
        pet = BreedingType.objects.create(name="pet")
        poultry = BreedingType.objects.create(name="poultry")
        pet_org, _ = self._create_org_with_address(
            owner=owner,
            name="Pet Breeder",
            org_type=OrganizationType.BREEDER,
        )
        poultry_org, _ = self._create_org_with_address(
            owner=owner,
            name="Poultry Farm",
            org_type=OrganizationType.BREEDER,
        )
        BreedingTypeOrganizations.objects.create(
            organization=pet_org,
            breeding_type=pet,
        )
        BreedingTypeOrganizations.objects.create(
            organization=poultry_org,
            breeding_type=poultry,
        )

        response = self.client.get("/users/organization-filtering/?breeding-type=pet")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], pet_org.id)


class OrganizationRolePermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _create_org_with_owner(self):
        owner = User.objects.create_user(
            email="owner-role@example.com",
            password="secret",
            first_name="Owner",
            last_name="Role",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Role Shelter",
            email="role-shelter@example.com",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=organization,
            role=MemberRole.OWNER,
        )
        return owner, organization

    def test_volunteer_cannot_update_organization(self):
        owner, organization = self._create_org_with_owner()
        volunteer = User.objects.create_user(
            email="volunteer@example.com",
            password="secret",
            first_name="Volunteer",
            last_name="User",
        )
        OrganizationMember.objects.create(
            user=volunteer,
            organization=organization,
            role=MemberRole.VOLUNTEER,
        )

        self.client.force_authenticate(user=volunteer)
        response = self.client.patch(
            f"/users/organizations/{organization.id}/",
            {"name": "New Name", "email": "new-name@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_volunteer_cannot_add_organization_member(self):
        owner, organization = self._create_org_with_owner()
        volunteer = User.objects.create_user(
            email="volunteer-invite@example.com",
            password="secret",
            first_name="Volunteer",
            last_name="Invite",
        )
        invited_user = User.objects.create_user(
            email="new-member@example.com",
            password="secret",
            first_name="New",
            last_name="Member",
        )
        OrganizationMember.objects.create(
            user=volunteer,
            organization=organization,
            role=MemberRole.VOLUNTEER,
        )

        self.client.force_authenticate(user=volunteer)
        response = self.client.post(
            "/users/organization-members/",
            {
                "user": invited_user.id,
                "organization": organization.id,
                "role": MemberRole.STAFF,
                "invitation_confirmed": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class OrganizationAddressUpdateTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _create_owner_org(self):
        owner = User.objects.create_user(
            email="owner-address-update@example.com",
            password="secret",
            first_name="Owner",
            last_name="Update",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Update Shelter",
            email="update-shelter@example.com",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=organization,
            role=MemberRole.OWNER,
        )
        address = Address.objects.create(
            organization=organization,
            city="Poznań",
            street="Stara",
            house_number="5",
            zip_code="60-001",
        )
        return owner, organization, address

    def test_patch_updates_address(self):
        owner, organization, address = self._create_owner_org()
        self.client.force_authenticate(user=owner)

        payload = {
            "address": {
                "city": "Kraków",
                "street": "Nowa",
                "house_number": "10A",
                "zip_code": "30-001",
            }
        }

        response = self.client.patch(
            f"/users/organizations/{organization.id}/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        address.refresh_from_db()
        self.assertEqual(address.city, "Kraków")
        self.assertEqual(address.street, "Nowa")
        self.assertEqual(response.data["address"]["zip_code"], "30-001")

    def test_put_updates_address(self):
        owner, organization, address = self._create_owner_org()
        self.client.force_authenticate(user=owner)

        payload = {
            "type": OrganizationType.SHELTER,
            "name": "Updated Shelter",
            "email": "updated-shelter@example.com",
            "phone": "",
            "description": {},
            "rating": None,
            "address": {
                "city": "Gdańsk",
                "street": "Portowa",
                "house_number": "2",
                "zip_code": "80-001",
            },
        }

        response = self.client.put(
            f"/users/organizations/{organization.id}/",
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        address.refresh_from_db()
        self.assertEqual(address.city, "Gdańsk")
        self.assertEqual(address.street, "Portowa")
        self.assertEqual(response.data["address"]["zip_code"], "80-001")
