from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone






# ────────────────────────────────────────────────────────────
#  Abstrakcyjna klasa z polami czasu (created / updated / soft-delete)
# ────────────────────────────────────────────────────────────
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    # prościutki helper do soft-delete
    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


# ────────────────────────────────────────────────────────────
#  Komentarze (polimorficzne)
# ────────────────────────────────────────────────────────────
class Comment(TimeStampedModel):
    """
    Uniwersalny komentarz – może dotyczyć dowolnego modelu (Article, Post, Animal, Litter…).
    """

    MIN_BODY_LENGTH = 3

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="comments",
        null=True,
        blank=True,
    )

    # Polimorficzny klucz obcy
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id    = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    body   = models.TextField()
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Opcjonalna ocena 1-5 (np. dla zwierzaków).",
    )

    class Meta:
        db_table = "comments"
        indexes = [
            models.Index(fields=("content_type", "object_id"), name="idx_comment_target"),
        ]
        ordering = ("-created_at",)

    def _is_organization_comment(self) -> bool:
        return (
            self.content_type.app_label == "users"
            and self.content_type.model == "organization"
        )

    def _validate_body_length(self) -> None:
        if len((self.body or "").strip()) >= self.MIN_BODY_LENGTH:
            return

        raise ValidationError(
            {
                "body": ValidationError(
                    f"Komentarz musi mieć minimum {self.MIN_BODY_LENGTH} znaki.",
                    code="COMMENT_TOO_SHORT",
                )
            }
        )

    def _validate_organization_rating_required(self) -> None:
        if not self._is_organization_comment() or self.rating is not None:
            return

        raise ValidationError(
            {
                "rating": ValidationError(
                    "Ocena jest wymagana dla opinii o organizacji.",
                    code="COMMENT_RATING_REQUIRED",
                )
            }
        )

    def _refresh_organization_rating_from_comments(self) -> None:
        """Przelicza ocenę organizacji na podstawie ocenionych komentarzy."""
        if not self._is_organization_comment():
            return

        from users.models import Organization

        try:
            organization = Organization.objects.get(pk=self.object_id)
        except Organization.DoesNotExist:
            return

        avg_rating = Comment.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id,
            rating__isnull=False,
        ).aggregate(avg=Avg("rating"))["avg"]

        organization.rating = None if avg_rating is None else int(round(avg_rating))
        organization.save(update_fields=["rating", "updated_at"])

    def _validate_single_organization_rating_per_user(self) -> None:
        """Pozwala użytkownikowi wystawić tylko jedną ocenę komentarzem dla organizacji."""
        if not self.user_id or self.rating is None:
            return

        if not self._is_organization_comment():
            return

        existing_rating = Comment.objects.filter(
            user_id=self.user_id,
            content_type=self.content_type,
            object_id=self.object_id,
            rating__isnull=False,
        )

        if self.pk:
            existing_rating = existing_rating.exclude(pk=self.pk)

        if existing_rating.exists():
            raise ValidationError(
                {
                    "rating": ValidationError(
                        "Użytkownik może wystawić tylko jedną ocenę dla tej organizacji.",
                        code="COMMENT_RATING_ALREADY_EXISTS",
                    )
                }
            )

    def clean(self) -> None:
        super().clean()
        self._validate_body_length()
        self._validate_organization_rating_required()
        self._validate_single_organization_rating_per_user()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self._refresh_organization_rating_from_comments()

    def delete(self, *args, **kwargs):
        organization_content_type = self.content_type
        organization_object_id = self.object_id
        is_organization_comment = (
            organization_content_type.app_label == "users"
            and organization_content_type.model == "organization"
        )

        super().delete(*args, **kwargs)

        if not is_organization_comment:
            return

        from users.models import Organization

        try:
            organization = Organization.objects.get(pk=organization_object_id)
        except Organization.DoesNotExist:
            return

        avg_rating = Comment.objects.filter(
            content_type=organization_content_type,
            object_id=organization_object_id,
            rating__isnull=False,
        ).aggregate(avg=Avg("rating"))["avg"]

        organization.rating = None if avg_rating is None else int(round(avg_rating))
        organization.save(update_fields=["rating", "updated_at"])

    def __str__(self) -> str:
        return f"{self.user_id} → {self.content_type.app_label}.{self.content_type.model}#{self.object_id}"


# ────────────────────────────────────────────────────────────
#  Reakcje / polubienia (polimorficzne)
# ────────────────────────────────────────────────────────────
class ReactionType(models.TextChoices):
    LIKE = "LIKE", "👍 Like"
    LOVE = "LOVE", "❤️ Love"
    WOW  = "WOW",  "😮 Wow"
    SAD  = "SAD",  "😢 Sad"
    ANGRY = "ANGRY", "😡 Angry"


class Reaction(TimeStampedModel):
    """
    Uniwersalna reakcja (like/love/…) powiązana z dowolnym obiektem.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reactions",
        null=True,
        blank=True,
    )

    reaction_type = models.CharField(
        max_length=10,
        choices=ReactionType.choices,
        default=ReactionType.LIKE,
    )

    # Polimorficzny klucz obcy
    reactable_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    reactable_id   = models.PositiveBigIntegerField()
    reactable_object = GenericForeignKey("reactable_type", "reactable_id")

    class Meta:
        db_table = "reactions"
        indexes = [
            models.Index(fields=("reactable_type", "reactable_id"), name="idx_reaction_target"),
        ]
        constraints = [
            # jeden użytkownik może zareagować danym typem tylko raz na ten sam obiekt
            models.UniqueConstraint(
                fields=("user", "reaction_type", "reactable_type", "reactable_id"),
                name="uniq_user_reaction_per_object",
            )
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.user_id} {self.reaction_type} {self.reactable_type}.{self.reactable_id}"


User = get_user_model()


class Notification(models.Model):
    """Prosta notyfikacja systemowa skierowana do konkretnego użytkownika."""

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="actor_notifications"
    )
    verb = models.CharField(max_length=255)
    target_type = models.CharField(max_length=50)
    target_id = models.PositiveIntegerField()
    created_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("recipient", "is_read", "created_at"), name="idx_notification_rec_read"),
        ]

    def __str__(self) -> str:
        return f"{self.recipient_id} ← {self.actor_id}: {self.verb} {self.target_type}#{self.target_id}"


def default_follow_notification_preferences() -> dict[str, bool]:
    return {
        "posts": True,
        "status_changes": True,
        "comments": False,
    }


class Follow(TimeStampedModel):
    """Polimorficzna relacja obserwowania dowolnego obiektu."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follows",
    )

    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveBigIntegerField()
    target_object = GenericForeignKey("target_type", "target_id")

    notification_preferences = models.JSONField(
        default=default_follow_notification_preferences,
        blank=True,
    )

    class Meta:
        db_table = "follows"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("target_type", "target_id"), name="idx_follow_target"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "target_type", "target_id"),
                name="uniq_user_follow_per_target",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} follows {self.target_type.app_label}.{self.target_type.model}#{self.target_id}"
