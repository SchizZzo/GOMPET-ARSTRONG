from django.db import models

# Create your models here.
# articles/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation

from common.models import Comment


class TimeStampedModel(models.Model):
    """Wspólne pola czasu i soft-delete."""
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


class Article(TimeStampedModel):
    """
    Model zgodny z ERD (Articles):
    • slug UNIQUE
    • tytuł, treść, opcjonalny obraz
    • autor FK → users.User
    • komentarze (polimorficznie)
    """

    id      = models.BigAutoField(primary_key=True)
    slug    = models.SlugField(unique=True)
    title   = models.CharField(max_length=255)
    content = models.TextField()
    image   = models.URLField(blank=True)                # lub ImageField(upload_to=…)
    author  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="articles",
        on_delete=models.CASCADE,
    )

    comments = GenericRelation(
        Comment,
        related_query_name="articles"
    )

    class Meta:
        db_table = "articles"
        indexes  = [
            models.Index(fields=("created_at",), name="idx_article_created"),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title
