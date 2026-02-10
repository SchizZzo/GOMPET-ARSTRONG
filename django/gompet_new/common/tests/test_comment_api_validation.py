from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from rest_framework.test import APIClient
from django.test import TestCase

from users.models import Organization, OrganizationType


class CommentApiValidationTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_superuser(
            email="commenter@example.com",
            password="secret",
        )
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="secret",
            first_name="Owner",
            last_name="Test",
        )
        self.client.force_authenticate(self.user)

        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Shelter",
            email="shelter@example.com",
            image="",
            phone="",
            user=self.owner,
        )
        self.organization_ct = ContentType.objects.get_for_model(Organization)
        self.url = reverse("comment-list")

    def test_duplicate_organization_rating_returns_bad_request(self) -> None:
        payload = {
            "content_type": self.organization_ct.id,
            "object_id": self.organization.id,
            "body": "Great",
            "rating": 5,
        }

        first_response = self.client.post(self.url, payload, format="json")
        second_response = self.client.post(self.url, payload, format="json")

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            second_response.data,
            {
                "error": {
                    "code": "COMMENT_RATING_ALREADY_EXISTS",
                    "field": "rating",
                }
            },
        )

    def test_organization_comment_requires_rating_and_minimum_body(self) -> None:
        payload = {
            "content_type": self.organization_ct.id,
            "object_id": self.organization.id,
            "body": "x",
            "rating": None,
        }

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {
                "errors": [
                    {"code": "COMMENT_TOO_SHORT", "field": "body"},
                    {"code": "COMMENT_RATING_REQUIRED", "field": "rating"},
                ]
            },
        )
