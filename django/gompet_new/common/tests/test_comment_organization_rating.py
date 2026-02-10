from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from common.models import Comment
from users.models import Organization, OrganizationType


class CommentOrganizationRatingTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="owner-rating@example.com",
            password="secret",
            first_name="Owner",
            last_name="Rating",
        )
        self.author = User.objects.create_user(
            email="author-rating@example.com",
            password="secret",
            first_name="Author",
            last_name="Rating",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Rating Shelter",
            email="rating-shelter@example.com",
            image="",
            phone="",
            user=self.owner,
        )
        self.organization_ct = ContentType.objects.get_for_model(Organization)

    def _create_comment(self, rating: int | None) -> Comment:
        return Comment.objects.create(
            user=self.author,
            content_type=self.organization_ct,
            object_id=self.organization.id,
            body="Test comment",
            rating=rating,
        )

    def test_comment_rating_sets_organization_rating(self) -> None:
        self._create_comment(rating=4)

        self.organization.refresh_from_db()

        self.assertEqual(self.organization.rating, 4)

    def test_multiple_comment_ratings_are_averaged_and_rounded(self) -> None:
        self._create_comment(rating=4)
        self._create_comment(rating=5)

        self.organization.refresh_from_db()

        self.assertEqual(self.organization.rating, 4)

    def test_comment_without_rating_is_ignored_in_aggregate(self) -> None:
        self._create_comment(rating=5)
        self._create_comment(rating=None)

        self.organization.refresh_from_db()

        self.assertEqual(self.organization.rating, 5)


    def test_updating_comment_rating_recalculates_organization_rating(self) -> None:
        comment = self._create_comment(rating=2)

        comment.rating = 5
        comment.save(update_fields=["rating", "updated_at"])
        self.organization.refresh_from_db()

        self.assertEqual(self.organization.rating, 5)

    def test_deleting_last_rated_comment_clears_organization_rating(self) -> None:
        comment = self._create_comment(rating=3)

        comment.delete()
        self.organization.refresh_from_db()

        self.assertIsNone(self.organization.rating)
