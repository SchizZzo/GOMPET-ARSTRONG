from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Article

User = get_user_model()

class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email")

class ArticleSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Article
        fields = (
            "id",
            "slug",
            "title",
            "content",
            "image",
            "author",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("created_at", "updated_at", "deleted_at")

    def create(self, validated_data):
        # Set the author to the current user
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["author"] = request.user
        return super().create(validated_data)
    

class ArticlesLastSerializer(serializers.ModelSerializer):
    """
    Serializer for listing the last 10 articles with minimal fields.
    """

    class Meta:
        model = Article
        fields = (
            "id",
            "slug",
            "title",
            "image",
            "created_at",
        )
        read_only_fields = ("id", "created_at")