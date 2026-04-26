from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from unittest.mock import patch

from animals.models import Animal, AnimalStatus, Gender, Size
from common.models import Comment, Follow

from users.models import MemberRole, Organization, OrganizationMember, OrganizationType

from .models import Post


def grant_post_permissions(user, *codenames):
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))


class PostDeletionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )
        self.animal = Animal.objects.create(
            name="Rex",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            status=AnimalStatus.AVAILABLE,
            owner=self.user,
        )
        self.post = Post.objects.create(
            content="Sample post",
            author=self.user,
            animal=self.animal,
        )

    def test_delete_post_removes_related_comments(self):
        comment = Comment.objects.create(
            user=self.user,
            content_object=self.post,
            body="Test comment",
        )

        self.post.delete()

        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())


class PostOwnershipAPITests(APITestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            email="owner@example.com",
            password="password123",
            first_name="Owner",
            last_name="User",
        )
        self.other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password="password123",
            first_name="Other",
            last_name="User",
        )
        self.animal = Animal.objects.create(
            name="Burek",
            species="Dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
            status=AnimalStatus.AVAILABLE,
            owner=self.owner,
        )
        self.post = Post.objects.create(
            content="Initial post",
            author=self.owner,
            animal=self.animal,
        )
        grant_post_permissions(self.owner, "add_post", "change_post")
        grant_post_permissions(self.other_user, "add_post", "change_post")

    def test_owner_can_create_post_for_owned_animal(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "animal": self.animal.id,
            "content": "New post content",
        }

        response = self.client.post(reverse("post-list"), data=payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Post.objects.filter(content="New post content", author=self.owner).exists()
        )

    def test_other_user_cannot_create_post_for_foreign_animal(self):
        self.client.force_authenticate(user=self.other_user)
        payload = {
            "animal": self.animal.id,
            "content": "Attempted post",
        }

        response = self.client.post(reverse("post-list"), data=payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Post.objects.filter(content="Attempted post").exists())

    def test_owner_can_update_post_for_owned_animal(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            reverse("post-detail", args=[self.post.id]),
            data={"content": "Updated content"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "Updated content")

    def test_other_user_cannot_update_post_for_foreign_animal(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(
            reverse("post-detail", args=[self.post.id]),
            data={"content": "Hacked content"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertNotEqual(self.post.content, "Hacked content")


class PostOrganizationOwnershipAPITests(APITestCase):
    def setUp(self):
        self.org_owner = get_user_model().objects.create_user(
            email="post-org-owner@example.com",
            password="password123",
            first_name="Post",
            last_name="OrgOwner",
        )
        self.member = get_user_model().objects.create_user(
            email="post-org-member@example.com",
            password="password123",
            first_name="Post",
            last_name="Member",
        )
        self.outsider = get_user_model().objects.create_user(
            email="post-org-outsider@example.com",
            password="password123",
            first_name="Post",
            last_name="Outsider",
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Posts Organization",
            email="posts-organization@example.com",
            user=self.org_owner,
        )
        OrganizationMember.objects.create(
            user=self.org_owner,
            organization=self.organization,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        )
        OrganizationMember.objects.create(
            user=self.member,
            organization=self.organization,
            role=MemberRole.STAFF,
            invitation_confirmed=True,
        )
        grant_post_permissions(self.org_owner, "add_post")
        grant_post_permissions(self.member, "add_post")
        grant_post_permissions(self.outsider, "add_post")

    def test_organization_owner_can_create_post_for_organization(self):
        self.client.force_authenticate(user=self.org_owner)

        response = self.client.post(
            reverse("post-list"),
            {"organization": self.organization.id, "content": "Owner org post"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Post.objects.filter(
                organization=self.organization,
                content="Owner org post",
                author=self.org_owner,
            ).exists()
        )

    def test_organization_member_can_create_post_for_organization(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            reverse("post-list"),
            {"organization": self.organization.id, "content": "Member org post"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Post.objects.filter(
                organization=self.organization,
                content="Member org post",
                author=self.member,
            ).exists()
        )

    def test_outsider_cannot_create_post_for_organization(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            reverse("post-list"),
            {"organization": self.organization.id, "content": "Outsider org post"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Post.objects.filter(
                organization=self.organization,
                content="Outsider org post",
                author=self.outsider,
            ).exists()
        )


class PostFeedAPITests(APITestCase):
    def setUp(self):
        self.viewer = get_user_model().objects.create_user(
            email="viewer@example.com",
            password="password123",
            first_name="Viewer",
            last_name="User",
        )
        self.owner = get_user_model().objects.create_user(
            email="feed-owner@example.com",
            password="password123",
            first_name="Feed",
            last_name="Owner",
        )
        self.org_owner = get_user_model().objects.create_user(
            email="feed-org-owner@example.com",
            password="password123",
            first_name="Org",
            last_name="Owner",
        )

        self.animal = Animal.objects.create(
            name="Roki",
            species="Dog",
            gender=Gender.MALE,
            size=Size.SMALL,
            status=AnimalStatus.AVAILABLE,
            owner=self.owner,
        )
        self.organization = Organization.objects.create(
            type=OrganizationType.SHELTER,
            name="Feed Shelter",
            email="feed-shelter@example.com",
            user=self.org_owner,
        )

        self.animal_post = Post.objects.create(
            content="Animal followed post",
            author=self.owner,
            animal=self.animal,
        )
        self.org_post = Post.objects.create(
            content="Organization followed post",
            author=self.org_owner,
            organization=self.organization,
        )

        Follow.objects.create(
            user=self.viewer,
            target_type=ContentType.objects.get_for_model(Animal),
            target_id=self.animal.id,
            notification_preferences={
                "posts": True,
                "status_changes": True,
                "comments": False,
            },
        )
        Follow.objects.create(
            user=self.viewer,
            target_type=ContentType.objects.get_for_model(Organization),
            target_id=self.organization.id,
            notification_preferences={
                "posts": True,
                "status_changes": True,
                "comments": False,
            },
        )

    def _extract_results(self, response):
        data = response.data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def _create_unfollowed_posts(self, count, author_email_prefix):
        author = get_user_model().objects.create_user(
            email=f"{author_email_prefix}@example.com",
            password="password123",
            first_name="Out",
            last_name="Sider",
        )
        animal = Animal.objects.create(
            name=f"{author_email_prefix}-animal",
            species="Dog",
            gender=Gender.FEMALE,
            size=Size.SMALL,
            status=AnimalStatus.AVAILABLE,
            owner=author,
        )
        posts = []
        for index in range(count):
            posts.append(
                Post.objects.create(
                    content=f"Recommended post {author_email_prefix}-{index}",
                    author=author,
                    animal=animal,
                )
            )
        return posts

    def test_feed_returns_posts_for_followed_animals_and_organizations(self):
        self.client.force_authenticate(user=self.viewer)

        response = self.client.get(reverse("post-feed"))

        self.assertEqual(response.status_code, 200)
        results = self._extract_results(response)
        returned_ids = {item["id"] for item in results}
        self.assertIn(self.animal_post.id, returned_ids)
        self.assertIn(self.org_post.id, returned_ids)

    def test_feed_uses_8_to_2_ratio_for_recommended_posts(self):
        self.client.force_authenticate(user=self.viewer)

        recommended_posts = self._create_unfollowed_posts(1, "outsider")

        response = self.client.get(reverse("post-feed"))

        self.assertEqual(response.status_code, 200)
        results = self._extract_results(response)
        returned_ids = {item["id"] for item in results}
        self.assertIn(self.animal_post.id, returned_ids)
        self.assertIn(self.org_post.id, returned_ids)
        self.assertIn(recommended_posts[0].id, returned_ids)
        self.assertEqual(len(results), 3)

    def test_feed_each_page_keeps_8_followed_and_2_recommended_posts(self):
        self.client.force_authenticate(user=self.viewer)

        for index in range(14):
            Post.objects.create(
                content=f"Followed post {index}",
                author=self.owner,
                animal=self.animal,
            )

        recommended_posts = self._create_unfollowed_posts(4, "outsider-multi")

        page_1_response = self.client.get(reverse("post-feed"), {"page": 1})
        page_2_response = self.client.get(reverse("post-feed"), {"page": 2})

        self.assertEqual(page_1_response.status_code, 200)
        self.assertEqual(page_2_response.status_code, 200)

        page_1_results = self._extract_results(page_1_response)
        page_2_results = self._extract_results(page_2_response)

        page_1_ids = {item["id"] for item in page_1_results}
        page_2_ids = {item["id"] for item in page_2_results}

        recommended_ids = {post.id for post in recommended_posts}

        self.assertEqual(len(page_1_results), 10)
        self.assertEqual(len(page_2_results), 9)
        self.assertEqual(len(page_1_ids & recommended_ids), 2)
        self.assertEqual(len(page_2_ids & recommended_ids), 2)

    def test_feed_allows_anonymous_access(self):
        response = self.client.get(reverse("post-feed"))

        self.assertEqual(response.status_code, 200)
        results = self._extract_results(response)
        returned_ids = {item["id"] for item in results}
        self.assertIn(self.animal_post.id, returned_ids)
        self.assertIn(self.org_post.id, returned_ids)


class PostErrorResponseFormatTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="posts-user@example.com",
            password="password123",
            first_name="Posts",
            last_name="User",
        )
        self.admin_user = get_user_model().objects.create_superuser(
            email="posts-admin@example.com",
            password="password123",
            first_name="Posts",
            last_name="Admin",
        )
        self.owner = get_user_model().objects.create_user(
            email="posts-owner@example.com",
            password="password123",
            first_name="Posts",
            last_name="Owner",
        )
        self.animal = Animal.objects.create(
            name="FormatDog",
            species="Dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
            status=AnimalStatus.AVAILABLE,
            owner=self.owner,
        )

    def test_401_error_payload_format(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.value")
        response = self.client.post(
            reverse("post-list"),
            {"animal": self.animal.id, "content": "Attempt"},
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
            reverse("post-list"),
            {"animal": self.animal.id, "content": "Attempt"},
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
        response = self.client.get(reverse("post-detail", args=[999999]))

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
            reverse("post-list"),
            {"animal": self.animal.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], 400)
        self.assertEqual(response.data["code"], "ERR_GENERIC_VALIDATION")
        self.assertEqual(response.data["message"], "Validation error.")
        self.assertIn("content", response.data["errors"])

    def test_500_error_payload_format(self):
        with patch("posts.api_views.PostViewSet.list", side_effect=RuntimeError("boom")):
            response = self.client.get(reverse("post-list"))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.data,
            {
                "status": 500,
                "code": "ERR_INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred.",
                "errors": {},
            },
        )
