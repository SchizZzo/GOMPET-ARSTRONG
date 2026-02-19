from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from animals.models import Animal, AnimalStatus, Gender, Size
from common.models import Comment, Follow

from users.models import Organization, OrganizationType

from .models import Post


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

    def test_owner_can_create_post_for_owned_animal(self):
        self.client.force_authenticate(user=self.owner)
        payload = {
            "animal": self.animal.id,
            "content": "New post content",
        }

        response = self.client.post("/posts/", data=payload, format="json")

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

        response = self.client.post("/posts/", data=payload, format="json")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Post.objects.filter(content="Attempted post").exists())

    def test_owner_can_update_post_for_owned_animal(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.patch(
            f"/posts/{self.post.id}/",
            data={"content": "Updated content"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "Updated content")

    def test_other_user_cannot_update_post_for_foreign_animal(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.patch(
            f"/posts/{self.post.id}/",
            data={"content": "Hacked content"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db()
        self.assertNotEqual(self.post.content, "Hacked content")


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
