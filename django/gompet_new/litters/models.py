from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from animals.models import Animal, LitterStatus
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from animals.models import AnimalsBreedGroups
from users.models import Species


# Create your models here.
# ────────────────────────────────────────────────────────────────────
#  Mioty
# ────────────────────────────────────────────────────────────────────
class Litter(models.Model):
    id          = models.BigAutoField(primary_key=True)
    species     = models.ForeignKey(
        Species,
        related_name="litters",
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    breed       = models.ForeignKey(
        AnimalsBreedGroups,
        related_name="litters",
        on_delete=models.CASCADE,
        null=True, blank=True
    )
    title       = models.CharField(max_length=255)
    description = models.JSONField(blank=True, null=True, help_text="Opis miotu w formacie JSON")
    birth_date  = models.DateField(null=True, blank=True)

    status      = models.CharField(max_length=10, choices=LitterStatus.choices, default=LitterStatus.ACTIVE)

    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="litters",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    organization = models.ForeignKey(
        "users.Organization",
        related_name="litters",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    comments    = GenericRelation("common.Comment", related_query_name="litters")
    reactions   = GenericRelation(
        "common.Reaction",
        related_query_name="litters",
        content_type_field="reactable_type",
        object_id_field="reactable_id",
    )

    

    class Meta:
        db_table = "litters"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(owner__isnull=False) & models.Q(organization__isnull=True))
                    | (models.Q(owner__isnull=True) & models.Q(organization__isnull=False))
                ),
                name="exactly_one_owner_fk",
            ),
        ]
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["organization"]),
        ]

    def clean(self):
        super().clean()
        if not (bool(self.owner) ^ bool(self.organization)):
            raise ValidationError(
                {"__all__": _("Musisz wskazać dokładnie jedno z pól: „owner” lub „organization”.")}
            )

    def __str__(self) -> str:
        return self.title or f"Litter #{self.id}"
    
    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])




class LitterAnimal(models.Model):
    """
    Join-table litter ↔ animal
    """
    id         = models.BigAutoField(primary_key=True)
    litter     = models.ForeignKey(Litter, on_delete=models.CASCADE, related_name="litter_animals")
    animal     = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name="animal_litters")

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table   = "litter_animals"
        constraints = [
            models.UniqueConstraint(fields=("litter", "animal"), name="uniq_litter_animal")
        ]

    def __str__(self) -> str:
        return f"L{self.litter_id}-A{self.animal_id}"