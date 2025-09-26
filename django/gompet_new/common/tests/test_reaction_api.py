from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from animals.models import Animal, Gender, Size
from articles.models import Article
from common.models import Comment, Reaction, ReactionType
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
        self.has_reaction_url = reverse("reaction-has-reaction")

        self.article = Article.objects.create(
            slug="test-article",
            title="Test Article",
            content="Some content",
            author=self.user,
        )

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

    def test_has_reaction_returns_true_for_post(self) -> None:
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

        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "posts.post",
                "reactable_id": post.id,
                "reaction_type": ReactionType.LIKE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_reaction"])

    def test_has_reaction_returns_true_for_article(self) -> None:
        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.LOVE,
            reactable_type=ContentType.objects.get_for_model(Article),
            reactable_id=self.article.id,
        )

        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "articles.article",
                "reactable_id": self.article.id,
                "reaction_type": ReactionType.LOVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_reaction"])

    def test_has_reaction_returns_true_for_comment(self) -> None:
        comment_target = Post.objects.create(
            content="Hello",
            author=self.user,
            animal=self.animal,
        )
        comment = Comment.objects.create(
            user=self.user,
            content_type=ContentType.objects.get_for_model(Post),
            object_id=comment_target.id,
            body="Nice!",
        )

        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.WOW,
            reactable_type=ContentType.objects.get_for_model(Comment),
            reactable_id=comment.id,
        )

        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "common.comment",
                "reactable_id": comment.id,
                "reaction_type": ReactionType.WOW,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_reaction"])

    def test_has_reaction_returns_false_when_no_reaction(self) -> None:
        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "articles.article",
                "reactable_id": self.article.id,
                "reaction_type": ReactionType.ANGRY,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["has_reaction"])

    def test_has_reaction_requires_parameters(self) -> None:
        response = self.client.get(self.has_reaction_url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_has_reaction_validates_reaction_type(self) -> None:
        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "articles.article",
                "reactable_id": self.article.id,
                "reaction_type": "invalid",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)

    def test_has_reaction_returns_false_for_anonymous_user(self) -> None:
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

        self.client.force_authenticate(user=None)

        response = self.client.get(
            self.has_reaction_url,
            {
                "reactable_type": "posts.post",
                "reactable_id": post.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["has_reaction"])
