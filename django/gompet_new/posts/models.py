from django.db import models, router, transaction

# Create your models here.
# posts/models.py
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from common.models import Comment, Reaction

from animals.models import Animal
from users.models import Organization




class TimeStampedModel(models.Model):
    """DRY helper: pola created/updated/deleted."""
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class Post(TimeStampedModel):
    """
    Model zgodny z tabelą 'Posts' na ERD:
    • tekst, opcjonalny obrazek,
    • autor (FK → users.User),
    • relacje polimorficzne: komentarze, reakcje.
    """

    content = models.TextField()
    image = models.ImageField(
        upload_to="posts/images/",
        null=True, blank=True)
    #image = models.URLField(null=True, blank=True)  # można też użyć ImageField(...)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        blank=True, null=True
    )
    animal = models.ForeignKey(
        Animal,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="posts"
    )
    organization = models.ForeignKey(
        Organization,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name="posts"
    )

    # powiązania generic
    comments = GenericRelation(
        Comment,
        related_query_name="posts"
    )
    reactions = GenericRelation(
        Reaction,
        related_query_name="posts",
        content_type_field="reactable_type",
        object_id_field="reactable_id",
    )

    

    class Meta:
        db_table = "posts"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(animal__isnull=False) & models.Q(organization__isnull=True))
                    | (models.Q(animal__isnull=True) & models.Q(organization__isnull=False))
                ),
                name="exactly_one_parent_fk"
            ),
        ]
        indexes = [
            models.Index(fields=["animal"]),
            models.Index(fields=["organization"]),
        ]

    def clean(self):
        super().clean()
        if not (bool(self.animal) ^ bool(self.organization)):
            raise ValidationError(
                {"__all__": _("Musisz wskazać dokładnie jedno z pól: „animal” lub „organization”.")}
            )

    def save(self, *args, **kwargs):
        # wymusza clean() nawet poza formularzem
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Post#{self.pk} by {self.author_id}"

    def soft_delete(self):
        """Wygodny helper soft-delete."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def delete(self, using=None, keep_parents=False):
        """Ensure that related generic comments are removed when deleting a post."""
        db_alias = using or self._state.db or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=db_alias):
            self.comments.using(db_alias).all().delete()
            return super().delete(using=db_alias, keep_parents=keep_parents)
