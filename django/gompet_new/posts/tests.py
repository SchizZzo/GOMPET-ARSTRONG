from django.contrib.auth import get_user_model
from django.test import TestCase

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
