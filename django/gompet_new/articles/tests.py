from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from common.models import Comment, Reaction, ReactionType

from .models import Article


class ArticleDeletionTests(TestCase):
    """Ensure article deletion handles related generic data."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="author@example.com",
            password="testpass123",
            first_name="Author",
            last_name="User",
        )

    def _create_article_with_relations(self, slug: str = "test-article"):
        article = Article.objects.create(
            slug=slug,
            title="Test Article",
            content="Content",
            author=self.user,
        )
        comment = Comment.objects.create(
            user=self.user,
            content_object=article,
            body="Comment",
        )
        reaction = Reaction.objects.create(
            user=self.user,
            reactable_object=article,
            reaction_type=ReactionType.LIKE,
        )
        return article, comment, reaction

    def test_soft_delete_marks_related_items(self):
        article, comment, reaction = self._create_article_with_relations("soft-delete-article")

        article.soft_delete()

        article.refresh_from_db()
        comment.refresh_from_db()
        reaction.refresh_from_db()

        self.assertIsNotNone(article.deleted_at)
        self.assertIsNotNone(comment.deleted_at)
        self.assertIsNotNone(reaction.deleted_at)

    def test_delete_removes_related_items(self):
        article, comment, reaction = self._create_article_with_relations("hard-delete-article")

        article.delete()

        self.assertFalse(Article.objects.filter(pk=article.pk).exists())
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())
        self.assertFalse(Reaction.objects.filter(pk=reaction.pk).exists())


class ArticleSlugTests(TestCase):
    """Ensure slugs are automatically generated from titles."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="author@example.com",
            password="testpass123",
            first_name="Author",
            last_name="User",
        )

    def test_slug_is_generated_from_title(self):
        article = Article.objects.create(
            title="My First Article",
            content="Content",
            author=self.user,
        )

        self.assertEqual(article.slug, "my-first-article")

    def test_slug_is_unique(self):
        Article.objects.create(
            title="Duplicate Title",
            content="Content",
            author=self.user,
        )

        article = Article.objects.create(
            title="Duplicate Title",
            content="Content",
            author=self.user,
        )

        self.assertEqual(article.slug, "duplicate-title-2")


class ArticleErrorResponseFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            email="articles-user@example.com",
            password="testpass123",
            first_name="Articles",
            last_name="User",
        )
        self.admin_user = User.objects.create_superuser(
            email="articles-admin@example.com",
            password="testpass123",
            first_name="Articles",
            last_name="Admin",
        )

    def test_401_error_payload_format(self):
        response = self.client.post(
            reverse("article-list"),
            {"title": "Article title", "content": "Article body"},
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

    def test_403_error_payload_format(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("article-list"),
            {"title": "Article title", "content": "Article body"},
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

    def test_404_error_payload_format(self):
        response = self.client.get(reverse("article-detail", args=["not-existing-slug"]))

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

    def test_400_validation_error_payload_format(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            reverse("article-list"),
            {"content": "Article body without title"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "validation_error")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertIn("title", response.data["errors"])
        self.assertEqual(len(response.data["errors"]["title"]), 1)
        self.assertEqual(response.data["errors"]["title"][0].code, "required")

    def test_500_error_payload_format(self):
        with patch("articles.api_views.ArticleViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get(reverse("article-list"))

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
