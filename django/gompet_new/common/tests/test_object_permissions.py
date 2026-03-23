from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from animals.models import Animal, Gender, Size
from common.models import Comment, Reaction, ReactionType


class CommentObjectPermissionTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.author = User.objects.create_user(
            email="comment-author@example.com",
            password="secret",
            first_name="Comment",
            last_name="Author",
        )
        self.intruder = User.objects.create_user(
            email="comment-intruder@example.com",
            password="secret",
            first_name="Comment",
            last_name="Intruder",
            is_staff=True,
        )
        self.intruder.user_permissions.add(
            Permission.objects.get(codename="change_comment"),
            Permission.objects.get(codename="delete_comment"),
        )

        self.animal = Animal.objects.create(
            name="CommentTarget",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.author,
        )
        self.comment = Comment.objects.create(
            user=self.author,
            content_type=ContentType.objects.get_for_model(Animal),
            object_id=self.animal.id,
            body="Author comment",
        )

    def test_user_with_model_permission_cannot_update_foreign_comment(self) -> None:
        self.client.force_authenticate(self.intruder)

        response = self.client.patch(
            reverse("comment-detail", args=[self.comment.id]),
            {"body": "Intruder edit"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Author comment")

    def test_user_with_model_permission_cannot_delete_foreign_comment(self) -> None:
        self.client.force_authenticate(self.intruder)

        response = self.client.delete(reverse("comment-detail", args=[self.comment.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())


class ReactionObjectPermissionTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        User = get_user_model()
        self.author = User.objects.create_user(
            email="reaction-author@example.com",
            password="secret",
            first_name="Reaction",
            last_name="Author",
        )
        self.intruder = User.objects.create_user(
            email="reaction-intruder@example.com",
            password="secret",
            first_name="Reaction",
            last_name="Intruder",
            is_staff=True,
        )
        self.intruder.user_permissions.add(
            Permission.objects.get(codename="change_reaction"),
            Permission.objects.get(codename="delete_reaction"),
        )

        self.animal = Animal.objects.create(
            name="ReactionTarget",
            species="Dog",
            gender=Gender.FEMALE,
            size=Size.MEDIUM,
            owner=self.author,
        )
        self.reaction = Reaction.objects.create(
            user=self.author,
            reaction_type=ReactionType.LIKE,
            reactable_type=ContentType.objects.get_for_model(Animal),
            reactable_id=self.animal.id,
        )

    def test_user_with_model_permission_cannot_update_foreign_reaction(self) -> None:
        self.client.force_authenticate(self.intruder)

        response = self.client.patch(
            reverse("reaction-detail", args=[self.reaction.id]),
            {"reaction_type": ReactionType.LOVE},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.reaction.refresh_from_db()
        self.assertEqual(self.reaction.reaction_type, ReactionType.LIKE)

    def test_user_with_model_permission_cannot_delete_foreign_reaction(self) -> None:
        self.client.force_authenticate(self.intruder)

        response = self.client.delete(reverse("reaction-detail", args=[self.reaction.id]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Reaction.objects.filter(id=self.reaction.id).exists())
