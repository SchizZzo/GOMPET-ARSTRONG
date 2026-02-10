from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from animals.models import Animal
from common.models import Comment, Notification, Reaction, ReactionType
from users.serializers import UserSerializer


class ContentTypeRelatedField(serializers.PrimaryKeyRelatedField):
    """Field accepting ContentType by PK or "app_label.model" string."""

    def __init__(self, **kwargs):
        super().__init__(queryset=ContentType.objects.all(), **kwargs)

    def to_internal_value(self, data):
        if isinstance(data, str) and "." in data:
            app_label, model = data.split(".", 1)
            app_label = app_label.lower()
            model = model.lower()
            try:
                return self.get_queryset().get(
                    app_label=app_label, model=model
                )
            except ContentType.DoesNotExist:
                self.fail("does_not_exist", pk_value=data)
        return super().to_internal_value(data)


class CommentSerializer(serializers.ModelSerializer):
    # wybieramy ContentType po its PK lub etykiecie "app_label.model"
    content_type = ContentTypeRelatedField()
    # użytkownik z request.user (ukryte pole)
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    author = UserSerializer(source="user", read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "author",
            "content_type",
            "object_id",
            "body",
            "rating",
            "created_at",
            "updated_at",
            "deleted_at",
            "user",
        )
        read_only_fields = ("created_at", "updated_at", "deleted_at")
        extra_kwargs = {"user": {"write_only": True}}

    def validate(self, attrs):
        # optional: możesz tu dodać logikę walidacji np. rating 1-5
        return attrs

    def create(self, validated_data):
        try:
            return Comment.objects.create(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            ) from exc

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            ) from exc

        return instance


class ReactionSerializer(serializers.ModelSerializer):
    reactable_type = ContentTypeRelatedField()
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
        try:
            return Reaction.objects.create(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            ) from exc

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        try:
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, "message_dict", exc.messages)
            ) from exc

        return instance


class ContentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = ["id", "app_label", "model"]


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "actor",
            "verb",
            "target_type",
            "target_id",
            "created_object_id",
            "target_label",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "actor",
            "verb",
            "target_type",
            "target_id",
            "created_object_id",
            "target_label",
            "created_at",
        ]

    def get_target_label(self, obj: Notification) -> str | None:
        if obj.target_type != "animal":
            return None

        try:
            animal = Animal.objects.only("name").get(pk=obj.target_id)
        except Animal.DoesNotExist:
            return None

        return animal.name
