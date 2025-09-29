from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, router, transaction
from django.utils import timezone

from common.models import Comment, Reaction


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
    image = models.ImageField(
        upload_to="articles/images/",
        null=True, blank=True)
    author  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="articles",
        on_delete=models.CASCADE,
    )

    comments = GenericRelation(
        Comment,
        related_query_name="articles"
    )

    reactions = GenericRelation(
        Reaction,
        related_query_name="articles",
        content_type_field="reactable_type",
        object_id_field="reactable_id",
    )



    class Meta:
        db_table = "articles"
        indexes  = [
            models.Index(fields=("created_at",), name="idx_article_created"),
        ]
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.title

    def soft_delete(self):
        """Soft delete article together with its comments and reactions."""
        if self.deleted_at is not None:
            # already soft-deleted; no need to run cascade again
            return

        deleted_at = timezone.now()
        db_alias = self._state.db or router.db_for_write(type(self), instance=self)

        with transaction.atomic(using=db_alias):
            self.deleted_at = deleted_at
            self.save(update_fields=["deleted_at"])

            (self.comments
                 .using(db_alias)
                 .filter(deleted_at__isnull=True)
                 .update(deleted_at=deleted_at))

            (self.reactions
                 .using(db_alias)
                 .filter(deleted_at__isnull=True)
                 .update(deleted_at=deleted_at))

    def delete(self, using=None, keep_parents=False):
        """Hard delete article together with related generic data."""
        db_alias = using or self._state.db or router.db_for_write(type(self), instance=self)

        with transaction.atomic(using=db_alias):
            self.comments.using(db_alias).all().delete()
            self.reactions.using(db_alias).all().delete()
            return super().delete(using=db_alias, keep_parents=keep_parents)
