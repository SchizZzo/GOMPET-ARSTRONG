from __future__ import annotations
import os
import tempfile
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from rest_framework import serializers
from .serializers import Base64ImageField, UserUpdateSerializer



from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from rest_framework import serializers

from .models import (
    MemberRole,
    Organization,
    OrganizationType,
    OrganizationMember,
)
from .services import CannotDeleteUser, delete_user_account
from .serializers import Base64ImageField

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