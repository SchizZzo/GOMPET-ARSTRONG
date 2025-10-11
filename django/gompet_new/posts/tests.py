from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from animals.models import Animal, AnimalStatus, Gender, Size
from common.models import Comment

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
