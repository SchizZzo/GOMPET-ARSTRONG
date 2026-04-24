import re
from unittest.mock import patch
from collections import Counter

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from common.models import Comment, Reaction, ReactionType

from .models import Article, ArticleCategory, ArticleCategoryGroup


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
        self.assertEqual(response.data["errors"]["title"][0]["code"], "required")

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


class ArticleCategoryGroupsEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.baseline_counts = Counter(
            ArticleCategory.objects.filter(deleted_at__isnull=True).values_list("group", flat=True)
        )

        ArticleCategory.objects.create(
            name="Endpoint Basics Category",
            slug="endpoint-basics-category",
            group=ArticleCategoryGroup.BASICS,
        )
        ArticleCategory.objects.create(
            name="Endpoint Training Category",
            slug="endpoint-training-category",
            group=ArticleCategoryGroup.TRAINING,
        )

        deleted_health = ArticleCategory.objects.create(
            name="Endpoint Deleted Health Category",
            slug="endpoint-deleted-health-category",
            group=ArticleCategoryGroup.HEALTH,
        )
        deleted_health.deleted_at = timezone.now()
        deleted_health.save(update_fields=["deleted_at"])

    def test_groups_endpoint_returns_declared_groups_with_counts(self):
        response = self.client.get(reverse("article-category-groups"))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

        returned_values = [item["value"] for item in response.data]
        expected_values = [value for value, _ in ArticleCategoryGroup.choices]
        self.assertEqual(returned_values, expected_values)

        grouped = {item["value"]: item for item in response.data}

        for value, label in ArticleCategoryGroup.choices:
            self.assertIn(value, grouped)
            self.assertEqual(grouped[value]["label"], label)

        self.assertEqual(
            grouped[ArticleCategoryGroup.BASICS]["categories_count"],
            self.baseline_counts.get(ArticleCategoryGroup.BASICS, 0) + 1,
        )
        self.assertEqual(
            grouped[ArticleCategoryGroup.TRAINING]["categories_count"],
            self.baseline_counts.get(ArticleCategoryGroup.TRAINING, 0) + 1,
        )
        self.assertEqual(
            grouped[ArticleCategoryGroup.HEALTH]["categories_count"],
            self.baseline_counts.get(ArticleCategoryGroup.HEALTH, 0),
        )


class ArticleCategoryListFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.health_category = ArticleCategory.objects.create(
            name="Filter Health Category",
            slug="filter-health-category",
            group=ArticleCategoryGroup.HEALTH,
        )
        self.shopping_category = ArticleCategory.objects.create(
            name="Filter Shopping Category",
            slug="filter-shopping-category",
            group=ArticleCategoryGroup.SHOPPING,
        )

        self.deleted_shopping_category = ArticleCategory.objects.create(
            name="Filter Deleted Shopping Category",
            slug="filter-deleted-shopping-category",
            group=ArticleCategoryGroup.SHOPPING,
        )
        self.deleted_shopping_category.deleted_at = timezone.now()
        self.deleted_shopping_category.save(update_fields=["deleted_at"])

    @staticmethod
    def _extract_results(data):
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_list_can_be_filtered_by_single_group(self):
        response = self.client.get(
            reverse("article-category-list"),
            {"group": ArticleCategoryGroup.HEALTH},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        names = {item["name"] for item in items}

        self.assertIn(self.health_category.name, names)
        self.assertNotIn(self.shopping_category.name, names)
        self.assertTrue(all(item["group"] == ArticleCategoryGroup.HEALTH for item in items))

    def test_list_can_be_filtered_by_multiple_groups_csv(self):
        response = self.client.get(
            reverse("article-category-list"),
            {"group": f"{ArticleCategoryGroup.HEALTH},{ArticleCategoryGroup.SHOPPING}"},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        names = {item["name"] for item in items}
        groups = {item["group"] for item in items}

        self.assertIn(self.health_category.name, names)
        self.assertIn(self.shopping_category.name, names)
        self.assertNotIn(self.deleted_shopping_category.name, names)
        self.assertTrue(
            groups.issubset({ArticleCategoryGroup.HEALTH, ArticleCategoryGroup.SHOPPING})
        )

    def test_list_can_be_filtered_by_groups_alias(self):
        response = self.client.get(
            reverse("article-category-list"),
            {"groups": ArticleCategoryGroup.SHOPPING},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        names = {item["name"] for item in items}

        self.assertIn(self.shopping_category.name, names)
        self.assertNotIn(self.health_category.name, names)
        self.assertNotIn(self.deleted_shopping_category.name, names)
        self.assertTrue(all(item["group"] == ArticleCategoryGroup.SHOPPING for item in items))

    def test_list_contains_code_for_each_category(self):
        response = self.client.get(reverse("article-category-list"))

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        self.assertTrue(items)
        self.assertTrue(all("code" in item and item["code"] for item in items))
        code_pattern = re.compile(r"^[A-Z0-9_]+$")
        self.assertTrue(all(code_pattern.match(item["code"]) for item in items))


class ArticleCategoryGroupFilterOnArticlesTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.author = User.objects.create_user(
            email="filter-author@example.com",
            password="testpass123",
            first_name="Filter",
            last_name="Author",
        )

        self.health_category = ArticleCategory.objects.create(
            name="Articles Filter Health Category",
            slug="articles-filter-health-category",
            group=ArticleCategoryGroup.HEALTH,
        )
        self.shopping_category = ArticleCategory.objects.create(
            name="Articles Filter Shopping Category",
            slug="articles-filter-shopping-category",
            group=ArticleCategoryGroup.SHOPPING,
        )

        self.health_article = Article.objects.create(
            title="Health Filter Article",
            content={"body": "health"},
            author=self.author,
        )
        self.health_article.categories.add(self.health_category)

        self.shopping_article = Article.objects.create(
            title="Shopping Filter Article",
            content={"body": "shopping"},
            author=self.author,
        )
        self.shopping_article.categories.add(self.shopping_category)

        self.uncategorized_article = Article.objects.create(
            title="Uncategorized Filter Article",
            content={"body": "none"},
            author=self.author,
        )

        self.deleted_health_article = Article.objects.create(
            title="Deleted Health Filter Article",
            content={"body": "deleted"},
            author=self.author,
        )
        self.deleted_health_article.categories.add(self.health_category)
        self.deleted_health_article.deleted_at = timezone.now()
        self.deleted_health_article.save(update_fields=["deleted_at"])

    @staticmethod
    def _extract_results(data):
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_article_list_can_be_filtered_by_category_group(self):
        response = self.client.get(
            reverse("article-list"),
            {"category-group": ArticleCategoryGroup.HEALTH},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        slugs = {item["slug"] for item in items}

        self.assertIn(self.health_article.slug, slugs)
        self.assertNotIn(self.shopping_article.slug, slugs)
        self.assertNotIn(self.uncategorized_article.slug, slugs)
        self.assertNotIn(self.deleted_health_article.slug, slugs)

    def test_articles_latest_can_be_filtered_by_category_groups_alias(self):
        response = self.client.get(
            reverse("articles-latest-list"),
            {"category-groups": ArticleCategoryGroup.SHOPPING},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        slugs = {item["slug"] for item in items}

        self.assertIn(self.shopping_article.slug, slugs)
        self.assertNotIn(self.health_article.slug, slugs)
        self.assertNotIn(self.uncategorized_article.slug, slugs)
        self.assertNotIn(self.deleted_health_article.slug, slugs)

    def test_article_list_with_invalid_category_group_returns_empty(self):
        response = self.client.get(
            reverse("article-list"),
            {"category-group": "invalid-group"},
        )

        self.assertEqual(response.status_code, 200)
        items = self._extract_results(response.data)
        self.assertEqual(items, [])
