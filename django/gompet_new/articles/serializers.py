from rest_framework import serializers
from django.contrib.auth import get_user_model

from users.serializers import UserSerializer
from .models import Article, ArticleCategory

User = get_user_model()

class Base64ImageField(serializers.ImageField):
    """
    Przyjmuje data URI lub czysty base‑64 i konwertuje na ContentFile.
    """
    def to_internal_value(self, data):
        import base64, imghdr, uuid
        from django.core.files.base import ContentFile

        if isinstance(data, str) and data.startswith("data:image"):
            fmt, imgstr = data.split(";base64,")
            ext = imghdr.what(None, base64.b64decode(imgstr))
            file_name = f"{uuid.uuid4()}.{ext}"
            data = ContentFile(base64.b64decode(imgstr), name=file_name)
        return super().to_internal_value(data)

class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email")

class ArticleSerializer(serializers.ModelSerializer):
    #author = AuthorSerializer(read_only=True)
    comments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    image = Base64ImageField(required=False, allow_null=True)

    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ArticleCategory.objects.all(),
        required=False,
        allow_empty=True,
    )

    author = UserSerializer(read_only=True)

    class Meta:
        model = Article
        fields = (
            "id",
            "slug",
            "title",
            "content",
            "image",
            "author",

            "categories",

            "comments",
            "reactions",
            
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("slug", "created_at", "updated_at", "deleted_at", "comments", "reactions")


    def create(self, validated_data):
        categories = validated_data.pop("categories", [])
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["author"] = request.user
        article = super().create(validated_data)
        if categories:
            article.categories.set(categories)
        return article

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        
        article = super().update(instance, validated_data)
        if categories is not None:
            article.categories.set(categories)
        return article
    

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


class ArticleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArticleCategory
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "deleted_at")