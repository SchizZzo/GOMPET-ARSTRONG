from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from animals.models import Animal, Gender, Size
from common.models import Follow
from users.models import Organization, OrganizationType


class FollowViewSetTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="follower@example.com",
            password="secret",
            first_name="Follower",
            last_name="User",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="secret",
            first_name="Other",
            last_name="User",
        )

        self.animal = Animal.objects.create(
            name="Burek",
            species="Dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
            owner=self.other,
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Safe Paws",
            email="org@example.com",
            user=self.other,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.follow_list_url = reverse("follow-list")
        self.follow_is_following_url = reverse("follow-is-following")
        self.follow_followers_count_url = reverse("follow-followers-count")

    def test_create_follow_for_animal(self) -> None:
        response = self.client.post(
            self.follow_list_url,
            {
                "target_type": "animals.animal",
                "target_id": self.animal.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Follow.objects.filter(
                user=self.user,
                target_type=ContentType.objects.get_for_model(Animal),
                target_id=self.animal.id,
            ).exists()
        )

    def test_create_follow_for_organization_with_preferences(self) -> None:
        response = self.client.post(
            self.follow_list_url,
            {
                "target_type": "users.organization",
                "target_id": self.organization.id,
                "notification_preferences": {
                    "posts": True,
                    "status_changes": False,
                    "comments": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        follow = Follow.objects.get(id=response.data["id"])
        self.assertEqual(
            follow.notification_preferences,
            {
                "posts": True,
                "status_changes": False,
                "comments": True,
            },
        )

    def test_create_follow_rejects_unsupported_preference_key(self) -> None:
        response = self.client.post(
            self.follow_list_url,
            {
                "target_type": "animals.animal",
                "target_id": self.animal.id,
                "notification_preferences": {
                    "posts": True,
                    "unknown": True,
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("notification_preferences", response.data)

    def test_create_follow_rejects_duplicate_follow(self) -> None:
        Follow.objects.create(
            user=self.user,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )

        response = self.client.post(
            self.follow_list_url,
            {
                "target_type": "animals.animal",
                "target_id": self.animal.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_list_returns_only_current_user_follows(self) -> None:
        Follow.objects.create(
            user=self.user,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )
        Follow.objects.create(
            user=self.other,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )

        response = self.client.get(self.follow_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_is_following_returns_follow_id_when_exists(self) -> None:
        follow = Follow.objects.create(
            user=self.user,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )

        response = self.client.get(
            self.follow_is_following_url,
            {
                "target_type": "animals.animal",
                "target_id": self.animal.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["follow_id"], follow.id)

    def test_is_following_returns_zero_when_missing(self) -> None:
        response = self.client.get(
            self.follow_is_following_url,
            {
                "target_type": "users.organization",
                "target_id": self.organization.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["follow_id"], 0)

    def test_followers_count_returns_count_for_animal(self) -> None:
        Follow.objects.create(
            user=self.user,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )
        Follow.objects.create(
            user=self.other,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
        )

        response = self.client.get(
            self.follow_followers_count_url,
            {
                "target_type": "animals.animal",
                "target_id": self.animal.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["followers_count"], 2)

    def test_followers_count_rejects_unsupported_target_type(self) -> None:
        response = self.client.get(
            self.follow_followers_count_url,
            {
                "target_type": "common.comment",
                "target_id": 1,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "'target_type' must be users.organization or animals.animal.",
        )
