from django.contrib.auth import get_user_model
from django.test import TestCase

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
