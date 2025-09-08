
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from common.models import Comment, Reaction, ReactionType



class CommentSerializer(serializers.ModelSerializer):
    # wybieramy ContentType po its PK
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all()
    )
    # użytkownik z request.user (ukryte pole)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Comment
        fields = (
            "id",
            "user",
            "content_type",
            "object_id",
            "body",
            "rating",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("created_at", "updated_at", "deleted_at")

    def validate(self, attrs):
        # optional: możesz tu dodać logikę walidacji np. rating 1-5
        return attrs

    def create(self, validated_data):
        return Comment.objects.create(**validated_data)


class ReactionSerializer(serializers.ModelSerializer):
    reactable_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all()
    )
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Reaction
        fields = (
            "id",
            "user",
            "reaction_type",
            "reactable_type",
            "reactable_id",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        read_only_fields = ("created_at", "updated_at", "deleted_at")

    def validate_reaction_type(self, value):
        # upewnij się, że podany typ jest wśród dostępnych
        choices = [c[0] for c in ReactionType.choices]
        if value not in choices:
            raise serializers.ValidationError(f"Invalid reaction type: {value}")
        return value

    def create(self, validated_data):
        return Reaction.objects.create(**validated_data)
    

class ContentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = ["id", "app_label", "model"]