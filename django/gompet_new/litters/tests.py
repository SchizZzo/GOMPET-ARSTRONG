from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import MemberRole, Organization, OrganizationMember, OrganizationType

from .models import Litter


class LitterErrorResponseFormatTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email="litters-user@example.com",
            password="secret",
            first_name="Litters",
            last_name="User",
        )
        self.admin_user = User.objects.create_superuser(
            email="litters-admin@example.com",
            password="secret",
            first_name="Litters",
            last_name="Admin",
        )
        self.owner = User.objects.create_user(
            email="litters-owner@example.com",
            password="secret",
            first_name="Litters",
            last_name="Owner",
        )

    def test_401_error_payload_format(self) -> None:
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.value")
        response = self.client.get(reverse("litter-list"))

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

    def test_403_error_payload_format(self) -> None:
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("litter-list"),
            {
                "title": "Spring Litter",
                "owner": self.owner.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data,
            {
                "status": 403,
                "code": "permission_denied",
                "message": "You do not have permission to perform this action.",
                "errors": {},
            },
        )

    def test_404_error_payload_format(self) -> None:
        response = self.client.get(reverse("litter-detail", args=[999999]))

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

    def test_400_validation_error_payload_format(self) -> None:
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("litter-list"),
            {
                "owner": self.owner.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertIn("title", response.data["errors"])

    def test_500_error_payload_format(self) -> None:
        with patch("litters.api_views.LitterViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get(reverse("litter-list"))

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


class LitterPermissionTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="litter-owner@example.com",
            password="secret",
            first_name="Litter",
            last_name="Owner",
        )
        self.other_owner = User.objects.create_user(
            email="litter-other-owner@example.com",
            password="secret",
            first_name="Litter",
            last_name="OtherOwner",
        )
        self.member = User.objects.create_user(
            email="litter-member@example.com",
            password="secret",
            first_name="Litter",
            last_name="Member",
        )
        self.outsider = User.objects.create_user(
            email="litter-outsider@example.com",
            password="secret",
            first_name="Litter",
            last_name="Outsider",
        )
        self.admin_user = User.objects.create_superuser(
            email="litter-admin2@example.com",
            password="secret",
            first_name="Litter",
            last_name="Admin",
        )

        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Litters Shelter",
            email="litters-shelter@example.com",
            user=self.owner,
        )
        OrganizationMember.objects.create(
            user=self.owner,
            organization=self.organization,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        OrganizationMember.objects.create(
            user=self.member,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )

    def test_non_superuser_cannot_create_litter_for_other_owner(self) -> None:
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            reverse("litter-list"),
            {"title": "Spoofed Owner", "owner": self.other_owner.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Litter.objects.filter(title="Spoofed Owner").exists())

    def test_organization_member_can_create_litter_for_organization(self) -> None:
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            reverse("litter-list"),
            {"title": "Org Litter", "organization": self.organization.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        litter = Litter.objects.get(id=response.data["id"])
        self.assertEqual(litter.organization_id, self.organization.id)
        self.assertIsNone(litter.owner_id)

    def test_outsider_cannot_create_litter_for_organization(self) -> None:
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            reverse("litter-list"),
            {"title": "Outsider Org Litter", "organization": self.organization.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Litter.objects.filter(title="Outsider Org Litter").exists())

    def test_non_superuser_cannot_reassign_litter_owner(self) -> None:
        litter = Litter.objects.create(title="Owned litter", owner=self.owner)
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("litter-detail", args=[litter.id]),
            {"owner": self.other_owner.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        litter.refresh_from_db()
        self.assertEqual(litter.owner_id, self.owner.id)

    def test_superuser_can_reassign_litter_owner(self) -> None:
        litter = Litter.objects.create(title="Admin owned litter", owner=self.owner)
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            reverse("litter-detail", args=[litter.id]),
            {"owner": self.other_owner.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        litter.refresh_from_db()
        self.assertEqual(litter.owner_id, self.other_owner.id)
