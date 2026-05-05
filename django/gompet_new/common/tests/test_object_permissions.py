from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from animals.models import Animal, Gender, Size
from common.models import Comment, Reaction, ReactionType
from users.models import MemberRole, Organization, OrganizationMember


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
        self.org_owner = User.objects.create_user(
            email="comment-org-owner@example.com",
            password="secret",
            first_name="Comment",
            last_name="OrgOwner",
        )
        self.intruder = User.objects.create_user(
            email="comment-intruder@example.com",
            password="secret",
            first_name="Comment",
            last_name="Intruder",
            is_staff=True,
        )
        self.same_org_moderator = User.objects.create_user(
            email="comment-moderator-same-org@example.com",
            password="secret",
            first_name="Comment",
            last_name="ModeratorSameOrg",
            is_staff=True,
        )
        self.other_org_moderator = User.objects.create_user(
            email="comment-moderator-other-org@example.com",
            password="secret",
            first_name="Comment",
            last_name="ModeratorOtherOrg",
            is_staff=True,
        )
        self.same_org_staff_member = User.objects.create_user(
            email="comment-staff-same-org@example.com",
            password="secret",
            first_name="Comment",
            last_name="StaffSameOrg",
            is_staff=True,
        )
        self.intruder.user_permissions.add(
            Permission.objects.get(codename="change_comment"),
            Permission.objects.get(codename="delete_comment"),
        )
        moderation_permissions = [
            Permission.objects.get(codename="change_comment"),
            Permission.objects.get(codename="delete_comment"),
        ]
        self.same_org_moderator.user_permissions.add(*moderation_permissions)
        self.other_org_moderator.user_permissions.add(*moderation_permissions)
        self.same_org_staff_member.user_permissions.add(*moderation_permissions)

        self.organization = Organization.objects.create(
            user=self.org_owner,
            type="SHELTER",
            name="CommentOrg",
            email="comment-org@example.com",
        )
        self.other_organization = Organization.objects.create(
            user=self.org_owner,
            type="SHELTER",
            name="CommentOtherOrg",
            email="comment-other-org@example.com",
        )
        OrganizationMember.objects.create(
            user=self.same_org_moderator,
            organization=self.organization,
            role=MemberRole.MODERATOR,
            invitation_confirmed=True,
        )
        OrganizationMember.objects.create(
            user=self.other_org_moderator,
            organization=self.other_organization,
            role=MemberRole.MODERATOR,
            invitation_confirmed=True,
        )
        OrganizationMember.objects.create(
            user=self.same_org_staff_member,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )

        self.animal = Animal.objects.create(
            name="CommentTarget",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            owner=self.author,
            organization=self.organization,
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

    def test_same_organization_moderator_can_update_foreign_comment(self) -> None:
        self.client.force_authenticate(self.same_org_moderator)

        response = self.client.patch(
            reverse("comment-detail", args=[self.comment.id]),
            {"body": "Moderator edit"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Moderator edit")

    def test_same_organization_moderator_can_delete_foreign_comment(self) -> None:
        self.client.force_authenticate(self.same_org_moderator)

        response = self.client.delete(reverse("comment-detail", args=[self.comment.id]))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_other_organization_moderator_cannot_manage_foreign_comment(self) -> None:
        self.client.force_authenticate(self.other_org_moderator)

        response_update = self.client.patch(
            reverse("comment-detail", args=[self.comment.id]),
            {"body": "Other moderator edit"},
            format="json",
        )
        response_delete = self.client.delete(reverse("comment-detail", args=[self.comment.id]))

        self.assertEqual(response_update.status_code, 403)
        self.assertEqual(response_delete.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Author comment")
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    def test_same_organization_non_moderation_member_cannot_manage_foreign_comment(self) -> None:
        self.client.force_authenticate(self.same_org_staff_member)

        response_update = self.client.patch(
            reverse("comment-detail", args=[self.comment.id]),
            {"body": "Staff edit"},
            format="json",
        )
        response_delete = self.client.delete(reverse("comment-detail", args=[self.comment.id]))

        self.assertEqual(response_update.status_code, 403)
        self.assertEqual(response_delete.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.body, "Author comment")
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())

    def test_same_organization_moderator_can_update_comment_on_member_profile(self) -> None:
        profile_comment = Comment.objects.create(
            user=self.author,
            content_type=ContentType.objects.get_for_model(type(self.author)),
            object_id=self.author.id,
            body="Profile comment",
        )

        OrganizationMember.objects.create(
            user=self.author,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )

        self.client.force_authenticate(self.same_org_moderator)
        response = self.client.patch(
            reverse("comment-detail", args=[profile_comment.id]),
            {"body": "Moderator profile edit"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        profile_comment.refresh_from_db()
        self.assertEqual(profile_comment.body, "Moderator profile edit")

    def test_same_organization_moderator_can_update_nested_foreign_comment(self) -> None:
        parent_comment = Comment.objects.create(
            user=self.author,
            content_type=ContentType.objects.get_for_model(type(self.animal)),
            object_id=self.animal.id,
            body="Parent comment",
        )
        nested_comment = Comment.objects.create(
            user=self.intruder,
            content_type=ContentType.objects.get_for_model(Comment),
            object_id=parent_comment.id,
            body="Nested foreign comment",
        )

        self.client.force_authenticate(self.same_org_moderator)
        response = self.client.patch(
            reverse("comment-detail", args=[nested_comment.id]),
            {"body": "Moderator nested edit"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        nested_comment.refresh_from_db()
        self.assertEqual(nested_comment.body, "Moderator nested edit")


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
