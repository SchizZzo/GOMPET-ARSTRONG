from django.db import models

# Create your models here.


# common/models.py
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
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
