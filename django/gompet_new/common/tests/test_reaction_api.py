from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from animals.models import Animal, Gender, Size
from common.models import Reaction, ReactionType
from posts.models import Post


class ReactionViewSetTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email="like@example.com",
            password="secret",
            first_name="Like",
            last_name="Tester",
        )
        self.client.force_authenticate(self.user)

        self.animal = Animal.objects.create(
            name="Lubiak",
            species="Dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
        )
        self.content_type = ContentType.objects.get_for_model(Animal)
        self.remove_like_url = reverse("reaction-remove-like")
        self.is_liked_url = reverse("reaction-is-liked")

    def test_remove_like_deletes_existing_reaction(self) -> None:
        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        response = self.client.delete(
            self.remove_like_url,
            {
                "reactable_type": f"{self.content_type.app_label}.{self.content_type.model}",
                "reactable_id": self.animal.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Reaction.objects.filter(
                user=self.user,
                reaction_type=ReactionType.LIKE,
                reactable_type=self.content_type,
                reactable_id=self.animal.id,
            ).exists()
        )

    def test_remove_like_requires_parameters(self) -> None:
        response = self.client.delete(self.remove_like_url, {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_is_liked_returns_true_when_reaction_exists(self) -> None:
        post = Post.objects.create(
            content="Hello",
            author=self.user,
            animal=self.animal,
        )

        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.LIKE,
            reactable_type=ContentType.objects.get_for_model(Post),
            reactable_id=post.id,
        )

        response = self.client.get(self.is_liked_url, {"post_id": post.id})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_liked"])

    def test_is_liked_returns_false_when_no_reaction(self) -> None:
        post = Post.objects.create(
            content="Hello",
            author=self.user,
            animal=self.animal,
        )

        response = self.client.get(self.is_liked_url, {"post_id": post.id})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_liked"])

    def test_is_liked_requires_post_id(self) -> None:
        response = self.client.get(self.is_liked_url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_is_liked_returns_false_for_anonymous_user(self) -> None:
        post = Post.objects.create(
            content="Hello",
            author=self.user,
            animal=self.animal,
        )

        self.client.force_authenticate(user=None)

        response = self.client.get(self.is_liked_url, {"post_id": post.id})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_liked"])
