from __future__ import annotations
import os
import tempfile
from dataclasses import dataclass
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from rest_framework import serializers, status
from .serializers import (
    Base64ImageField,
    OrganizationCreateSerializer,
    OrganizationUpdateSerializer,
    UserUpdateSerializer,
)



from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase
from rest_framework import serializers
from common.models import Notification

from .models import (
    Address,
    MemberRole,
    Organization,
    OrganizationType,
    OrganizationMember,
    Species,
)
from .services import CannotDeleteUser, delete_user_account
from .serializers import Base64ImageField

User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, "U\u017cytkownik musi mie\u0107 adres e-mail"):
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
            invitation_confirmed=True,
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
            invitation_confirmed=True,
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
            invitation_confirmed=True,
        )
        inviter = User.objects.create_superuser(
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
        self.assertEqual(notification.verb, "wys\u0142a\u0142(a) zaproszenie do organizacji")
        self.assertEqual(notification.target_type, "organization")
        self.assertEqual(notification.target_id, org.id)

    def test_confirmation_sends_notification_to_owner(self):
        owner = User.objects.create_user(
            email="owner-confirm@example.com",
            password="secret",
            first_name="Owner",
            last_name="Confirm",
        )
        org = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Confirm Shelter",
            email="confirm-shelter@example.com",
            image="",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=org,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        invited = User.objects.create_user(
            email="invitee-confirm@example.com",
            password="secret",
            first_name="Invitee",
            last_name="Confirm",
        )
        membership = OrganizationMember.objects.create(
            user=invited,
            organization=org,
            role=MemberRole.STAFF,
            invitation_confirmed=False,
        )
        self.client.force_authenticate(user=invited)

        response = self.client.patch(
            f"/users/organization-members/{membership.id}/",
            {"invitation_confirmed": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification = Notification.objects.get(recipient=owner)
        self.assertEqual(notification.actor, invited)
        self.assertEqual(notification.verb, "potwierdzi\u0142(a) zaproszenie do organizacji")
        self.assertEqual(notification.target_type, "organization")
        self.assertEqual(notification.target_id, org.id)

    def test_removal_sends_notification_to_member(self):
        owner = User.objects.create_user(
            email="owner-remove@example.com",
            password="secret",
            first_name="Owner",
            last_name="Remove",
        )
        org = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Remove Shelter",
            email="remove-shelter@example.com",
            image="",
            phone="",
            user=owner,
        )
        OrganizationMember.objects.create(
            user=owner,
            organization=org,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        member = User.objects.create_user(
            email="member-remove@example.com",
            password="secret",
            first_name="Member",
            last_name="Remove",
        )
        membership = OrganizationMember.objects.create(
            user=member,
            organization=org,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )
        self.client.force_authenticate(user=owner)

        response = self.client.delete(
            f"/users/organization-members/{membership.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        notification = Notification.objects.get(recipient=member)
        self.assertEqual(notification.actor, owner)
        self.assertEqual(notification.verb, "usun\u0105\u0142(a) Ci\u0119 z organizacji")
        self.assertEqual(notification.target_type, "organization")
        self.assertEqual(notification.target_id, org.id)


class OrganizationMemberPatchRoleInputTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="owner-role-update@example.com",
            password="secret",
            first_name="Owner",
            last_name="RoleUpdate",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Role Update Shelter",
            email="role-update-shelter@example.com",
            image="",
            phone="",
            user=self.owner,
        )
        OrganizationMember.objects.create(
            user=self.owner,
            organization=self.organization,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        self.member_user = User.objects.create_user(
            email="member-role-update@example.com",
            password="secret",
            first_name="Member",
            last_name="RoleUpdate",
        )
        self.membership = OrganizationMember.objects.create(
            user=self.member_user,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )

    @staticmethod
    def _role_id(role_value):
        return next(
            index
            for index, role in enumerate(MemberRole, start=1)
            if role.value == role_value
        )

    def test_patch_accepts_role_id_instead_of_role_label(self):
        self.client.force_authenticate(user=self.owner)
        moderator_role_id = self._role_id(MemberRole.MODERATOR)

        response = self.client.patch(
            f"/users/organization-members/{self.membership.id}/",
            {"role": moderator_role_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.role, MemberRole.MODERATOR)
        self.assertEqual(response.data["role"], MemberRole.MODERATOR)


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

    def test_patch_rejects_admin_only_fields_for_non_superuser(self):
        user = User.objects.create_user(
            email="limited@example.com",
            password="secret",
            first_name="Limited",
            last_name="User",
            is_staff=False,
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            "/users/users/",
            {"is_staff": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], 400)
        self.assertIn("is_staff", response.data["errors"])
        user.refresh_from_db()
        self.assertFalse(user.is_staff)


class UserObjectPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="me@example.com",
            password="secret",
            first_name="Me",
            last_name="User",
        )
        self.other_user = User.objects.create_user(
            email="other-object@example.com",
            password="secret",
            first_name="Other",
            last_name="User",
        )

    def test_non_superuser_cannot_update_other_user_by_id(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f"/users/users/{self.other_user.id}/",
            {"first_name": "Changed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.other_user.refresh_from_db()
        self.assertNotEqual(self.other_user.first_name, "Changed")


class OrganizationMemberPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="org-owner@example.com",
            password="secret",
            first_name="Owner",
            last_name="Org",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Permissions Shelter",
            email="permissions-shelter@example.com",
            image="",
            phone="",
            user=self.owner,
        )
        OrganizationMember.objects.create(
            user=self.owner,
            organization=self.organization,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        self.member_user = User.objects.create_user(
            email="org-member@example.com",
            password="secret",
            first_name="Member",
            last_name="Org",
        )
        self.member_membership = OrganizationMember.objects.create(
            user=self.member_user,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=False,
        )
        self.outsider = User.objects.create_user(
            email="org-outsider@example.com",
            password="secret",
            first_name="Outsider",
            last_name="Org",
        )

    def test_non_owner_cannot_invite_member(self):
        invitee = User.objects.create_user(
            email="invitee-permissions@example.com",
            password="secret",
            first_name="Invitee",
            last_name="Org",
        )
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            "/users/organization-members/",
            {
                "user": invitee.id,
                "organization": self.organization.id,
                "role": MemberRole.STAFF,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            OrganizationMember.objects.filter(
                user=invitee,
                organization=self.organization,
            ).exists()
        )

    def test_non_owner_can_create_own_join_request(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            "/users/organization-members/",
            {
                "user": self.outsider.id,
                "organization": self.organization.id,
                "role": MemberRole.VOLUNTEER,
                "invitation_confirmed": True,
                "invitation_message": "Chce dolaczyc",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = OrganizationMember.objects.get(
            user=self.outsider,
            organization=self.organization,
        )
        self.assertEqual(membership.role, MemberRole.VOLUNTEER)
        self.assertFalse(membership.invitation_confirmed)

    def test_non_owner_cannot_request_owner_role(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            "/users/organization-members/",
            {
                "user": self.outsider.id,
                "organization": self.organization.id,
                "role": MemberRole.OWNER,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            OrganizationMember.objects.filter(
                user=self.outsider,
                organization=self.organization,
            ).exists()
        )

    def test_non_owner_cannot_create_membership_for_other_user(self):
        invitee = User.objects.create_user(
            email="invitee-other@example.com",
            password="secret",
            first_name="Invitee",
            last_name="Other",
        )
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            "/users/organization-members/",
            {
                "user": invitee.id,
                "organization": self.organization.id,
                "role": MemberRole.STAFF,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            OrganizationMember.objects.filter(
                user=invitee,
                organization=self.organization,
            ).exists()
        )

    def test_member_cannot_change_own_role(self):
        self.client.force_authenticate(user=self.member_user)

        response = self.client.patch(
            f"/users/organization-members/{self.member_membership.id}/",
            {"role": MemberRole.OWNER},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, MemberRole.STAFF)

    def test_member_can_confirm_own_invitation(self):
        self.client.force_authenticate(user=self.member_user)

        response = self.client.patch(
            f"/users/organization-members/{self.member_membership.id}/",
            {"invitation_confirmed": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member_membership.refresh_from_db()
        self.assertTrue(self.member_membership.invitation_confirmed)


class OrganizationMembershipCheckViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.member = User.objects.create_user(
            email="check-member@example.com",
            password="secret",
            first_name="Check",
            last_name="Member",
        )
        self.non_member = User.objects.create_user(
            email="check-non-member@example.com",
            password="secret",
            first_name="Check",
            last_name="NonMember",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Membership Check Shelter",
            email="membership-check@example.com",
            image="",
            phone="",
            user=self.member,
        )
        self.membership = OrganizationMember.objects.create(
            user=self.member,
            organization=self.organization,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )

    def test_requires_authentication(self):
        response = self.client.get(
            f"/users/organization/check-membership/{self.organization.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_membership_for_authenticated_user(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(
            f"/users/organization/check-membership/{self.organization.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_member"])
        self.assertEqual(response.data["organization_id"], self.organization.id)
        self.assertEqual(response.data["user_id"], self.member.id)
        self.assertEqual(response.data["membership_id"], self.membership.id)
        self.assertEqual(response.data["role"], MemberRole.OWNER)
        self.assertTrue(response.data["invitation_confirmed"])

    def test_returns_false_for_non_member(self):
        self.client.force_authenticate(user=self.non_member)

        response = self.client.get(
            f"/users/organization/check-membership/{self.organization.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_member"])
        self.assertEqual(response.data["organization_id"], self.organization.id)
        self.assertEqual(response.data["user_id"], self.non_member.id)
        self.assertIsNone(response.data["membership_id"])
        self.assertIsNone(response.data["role"])
        self.assertIsNone(response.data["invitation_confirmed"])


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


class OrganizationRetrieveSpeciesFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_retrieve_returns_species_id_and_uppercase_label(self):
        owner = User.objects.create_user(
            email="owner-retrieve-species@example.com",
            password="secret",
            first_name="Owner",
            last_name="Retrieve",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Retrieve Species Org",
            email="retrieve-species-org@example.com",
            phone="",
            user=owner,
        )
        address = Address.objects.create(
            organization=organization,
            city="Warsaw",
            street="Api",
            house_number="1",
            zip_code="00-001",
        )
        species = Species.objects.create(name="dog")
        Species.objects.filter(pk=species.pk).update(label="dog_label")
        species.refresh_from_db()
        address.species.set([species])

        response = self.client.get(f"/users/organizations/{organization.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        species_payload = response.data["address"]["species"]
        self.assertEqual(len(species_payload), 1)
        self.assertEqual(set(species_payload[0].keys()), {"id", "label"})
        self.assertEqual(species_payload[0]["id"], species.id)
        self.assertEqual(species_payload[0]["label"], "DOG_LABEL")


class OrganizationMemberRoleListViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_returns_roles_with_uppercase_english_label_and_numeric_value(self):
        response = self.client.get("/users/organization-member-roles/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("roles", response.data)
        roles = response.data["roles"]
        self.assertTrue(len(roles) > 0)

        for idx, role in enumerate(roles, start=1):
            self.assertEqual(role["value"], idx)
            self.assertEqual(role["label"], role["label"].upper())

        moderator_role = next((item for item in roles if item["label"] == "MODERATOR"), None)
        self.assertIsNotNone(moderator_role)
        self.assertIsInstance(moderator_role["value"], int)


class SpeciesViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_returns_species_name_uppercase_and_label_from_db(self):
        Species.objects.create(name="dog", description="canine")
        Species.objects.create(name="swinka morska", description="guinea pig")

        response = self.client.get("/users/species/")

        self.assertEqual(response.status_code, 200)
        results = response.data.get("results", response.data)
        self.assertTrue(len(results) >= 2)
        labels = {item["label"] for item in results}
        self.assertIn("DOG", labels)
        self.assertIn("GUINEA_PIG", labels)
        for item in results:
            self.assertIn("id", item)
            self.assertEqual(item["name"], item["name"].upper())

    def test_species_label_is_persisted_in_database(self):
        species = Species.objects.create(name="swinka morska", description="guinea pig")
        species.refresh_from_db()
        self.assertEqual(species.label, "GUINEA_PIG")


class OrganizationUpdateSerializerTests(TestCase):
    def test_updates_nested_address_fields(self):
        owner = User.objects.create_user(
            email="owner-update-address@example.com",
            password="secret",
            first_name="Owner",
            last_name="Address",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Aktualizacja Adresu",
            email="update-address@example.com",
            phone="",
            user=owner,
        )
        address = Address.objects.create(
            organization=organization,
            city="KrakĂłw",
            street="Stara",
            house_number="1",
            zip_code="30-001",
        )

        serializer = OrganizationUpdateSerializer(
            instance=organization,
            data={
                "name": "Aktualizacja Adresu 2",
                "address": {
                    "city": "GdaĹ„sk",
                    "street": "Nowa",
                    "house_number": "5",
                    "zip_code": "80-001",
                    "lat": None,
                    "lng": None,
                    "location": None,
                    "species": [],
                },
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()

        updated.refresh_from_db()
        address.refresh_from_db()

        self.assertEqual(updated.name, "Aktualizacja Adresu 2")
        self.assertEqual(address.city, "GdaĹ„sk")
        self.assertEqual(address.street, "Nowa")
        self.assertEqual(address.house_number, "5")
        self.assertEqual(address.zip_code, "80-001")

    def test_updates_nested_address_species(self):
        owner = User.objects.create_user(
            email="owner-update-species@example.com",
            password="secret",
            first_name="Owner",
            last_name="Species",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Aktualizacja GatunkĂłw",
            email="update-species@example.com",
            phone="",
            user=owner,
        )
        address = Address.objects.create(
            organization=organization,
            city="PoznaĹ„",
            street="LeĹ›na",
            house_number="7",
            zip_code="60-001",
        )
        dog = Species.objects.create(name=f"Dog-{owner.pk}")
        cat = Species.objects.create(name=f"Cat-{owner.pk}")
        address.species.set([dog])

        serializer = OrganizationUpdateSerializer(
            instance=organization,
            data={
                "address": {
                    "city": address.city,
                    "street": address.street,
                    "house_number": address.house_number,
                    "zip_code": address.zip_code,
                    "lat": address.lat,
                    "lng": address.lng,
                    "location": address.location,
                    "species": [cat.id],
                }
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        address.refresh_from_db()
        self.assertEqual(list(address.species.values_list("id", flat=True)), [cat.id])

    def test_create_uses_location_to_fill_city_when_city_missing(self):
        owner = User.objects.create_user(
            email="owner-create-location-city@example.com",
            password="secret",
            first_name="Owner",
            last_name="Create",
        )

        with mock.patch("users.models.Address.get_city", return_value="Warszawa"):
            serializer = OrganizationCreateSerializer(
                data={
                    "type": OrganizationType.SHELTER,
                    "name": "Organizacja z lokalizacji",
                    "email": "organization-location@example.com",
                    "phone": "",
                    "description": "",
                    "address": {
                        "street": "Nowy Swiat",
                        "house_number": "1",
                        "zip_code": "00-001",
                        "lat": 52.229676,
                        "lng": 21.012229,
                        "location": Point(21.012229, 52.229676),
                        "species": [],
                    },
                }
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            organization = serializer.save(user=owner)

        organization.refresh_from_db()
        organization.address.refresh_from_db()
        self.assertEqual(organization.address.city, "Warszawa")

    def test_update_location_without_city_recomputes_city(self):
        owner = User.objects.create_user(
            email="owner-update-location-city@example.com",
            password="secret",
            first_name="Owner",
            last_name="Update",
        )
        organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Aktualizacja Lokalizacji",
            email="update-location-city@example.com",
            phone="",
            user=owner,
        )
        address = Address.objects.create(
            organization=organization,
            city="Stare Miasto",
            street="Stara",
            house_number="7",
            zip_code="60-001",
            location=Point(17.000000, 51.000000),
        )

        with mock.patch("users.models.Address.get_city", return_value="Krakow"):
            serializer = OrganizationUpdateSerializer(
                instance=organization,
                data={
                    "address": {
                        "street": address.street,
                        "house_number": address.house_number,
                        "zip_code": address.zip_code,
                        "lat": 50.061430,
                        "lng": 19.936580,
                        "location": Point(19.936580, 50.061430),
                        "species": [],
                    }
                },
                partial=True,
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            serializer.save()

        address.refresh_from_db()
        self.assertEqual(address.city, "Krakow")


class UserErrorResponseFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="users-format@example.com",
            password="secret123",
            first_name="Users",
            last_name="Format",
        )
        self.other_user = User.objects.create_user(
            email="users-format-other@example.com",
            password="secret123",
            first_name="Users",
            last_name="Other",
        )

    def test_401_error_payload_format(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.value")
        response = self.client.get("/users/users/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
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
        response = self.client.delete(f"/users/users/{self.other_user.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
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
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/users/users/999999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
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
        response = self.client.post(
            "/users/users/",
            {
                "email": "new-user@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "StrongPass123!",
                "confirm_password": "DifferentPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertIn("confirm_password", response.data["errors"])

    def test_400_manual_error_payload_format(self):
        response = self.client.post(
            "/users/auth/password-reset/confirm/",
            {
                "uid": "invalid",
                "token": "invalid",
                "new_password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertEqual(
            response.data["errors"],
            {"detail": "Nieprawid\u0142owy lub wygas\u0142y token resetu has\u0142a."},
        )

    def test_500_error_payload_format(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch("users.api_views.UserViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get("/users/users/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.data,
            {
                "status": 500,
                "code": "server_error",
                "message": "An internal server error occurred.",
                "errors": {},
            },
        )

