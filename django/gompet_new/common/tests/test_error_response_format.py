from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import Organization, OrganizationType


class CommonErrorResponseFormatTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()

        self.user = User.objects.create_user(
            email="common-user@example.com",
            password="secret",
            first_name="Common",
            last_name="User",
        )
        self.admin_user = User.objects.create_superuser(
            email="common-admin@example.com",
            password="secret",
            first_name="Common",
            last_name="Admin",
        )
        self.owner = User.objects.create_user(
            email="common-owner@example.com",
            password="secret",
            first_name="Common",
            last_name="Owner",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Common Shelter",
            email="common-shelter@example.com",
            user=self.owner,
        )
        self.organization_ct = ContentType.objects.get_for_model(Organization)
        self.comment_payload = {
            "content_type": self.organization_ct.id,
            "object_id": self.organization.id,
            "body": "Sample comment body",
            "rating": 5,
        }

    def test_401_error_payload_format(self) -> None:
        response = self.client.post(
            reverse("comment-list"),
            self.comment_payload,
            format="json",
        )

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
            reverse("comment-list"),
            self.comment_payload,
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
        response = self.client.get(reverse("comment-detail", args=[999999]))

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
            reverse("comment-list"),
            {
                "content_type": self.organization_ct.id,
                "object_id": self.organization.id,
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "ERR_GENERIC_VALIDATION")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertIn("body", response.data["errors"])

    def test_400_manual_error_payload_format(self) -> None:
        response = self.client.get(reverse("follow-followers-count"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "ERR_GENERIC_VALIDATION")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertEqual(
            response.data["errors"],
            {
                "detail": {
                    "code": "ERR_MISSING_TARGET_PARAMS",
                    "message": "Query parameters 'target_type' and 'target_id' are required.",
                }
            },
        )

    def test_500_error_payload_format(self) -> None:
        with patch("common.api_views.CommentViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get(reverse("comment-list"))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data,
            {
                "status": 500,
                "code": "ERR_INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "errors": {},
            },
        )
