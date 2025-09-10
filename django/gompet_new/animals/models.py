from django.db import models

# Create your models here.


from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError

from django.contrib.postgres.fields import ArrayField

from django.contrib.postgres.indexes import GinIndex

# ────────────────────────────────────────────────────────────────────
#  Enums / Choices
# ────────────────────────────────────────────────────────────────────
class Gender(models.TextChoices):
    MALE   = "MALE",   "Male"
    FEMALE = "FEMALE", "Female"
    OTHER  = "OTHER",  "Other"


class Size(models.TextChoices):
    SMALL  = "SMALL",  "Small"
    MEDIUM = "MEDIUM", "Medium"
    LARGE  = "LARGE",  "Large"


class AnimalStatus(models.TextChoices):
    AVAILABLE   = "AVAILABLE",   "Available"
    RESERVED    = "RESERVED",    "Reserved"
    ADOPTED     = "ADOPTED",     "Adopted"
    NOT_LISTED  = "NOT_LISTED",  "Hidden / Internal"


class ParentRelation(models.TextChoices):
    MOTHER      = "MOTHER",      "Mother"
    FATHER      = "FATHER",      "Father"
    #GUARDIAN    = "GUARDIAN",    "Guardian"


class LitterStatus(models.TextChoices):
    ACTIVE   = "ACTIVE",   "Active"
    CLOSED   = "CLOSED",   "Closed"
    DRAFT    = "DRAFT",    "Draft"


# ────────────────────────────────────────────────────────────────────
#  Core Animal model
# ────────────────────────────────────────────────────────────────────
class Animal(models.Model):
    id          = models.BigAutoField(primary_key=True)

    # podstawowe pola
    name        = models.CharField(max_length=150)
    descriptions = models.JSONField(blank=True, null=True, help_text="Opis zwierzęcia")

    image       = models.ImageField(
        upload_to="animals/images/",
        blank=True,
        null=True,
        help_text="Zalecany rozmiar: 800x600px"
    )
    species     = models.CharField(max_length=80)
    breed       = models.CharField(max_length=120, blank=True)
    gender      = models.CharField(max_length=6, choices=Gender.choices)
    size        = models.CharField(max_length=6, choices=Size.choices)
    birth_date  = models.DateField(null=True, blank=True)

    # właściciel (np. użytkownik lub organizacja – tutaj user)
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="animals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    status      = models.CharField(max_length=20, choices=AnimalStatus.choices, default=AnimalStatus.AVAILABLE)
    price       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    city       = models.CharField(max_length=100, blank=True)
    location    = gis_models.PointField(null=True, blank=True, geography=True)

    characteristic_board = models.JSONField(default=list, blank=True)

    
    

    


    # audit
    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    # komentarze i reakcje (polimorficzne)
    comments    = GenericRelation("common.Comment", related_query_name="animals")
    reactions   = GenericRelation(
        "common.Reaction",
        related_query_name="animals",
        content_type_field="reactable_type",
        object_id_field="reactable_id",
    )

    animal_weight_ranges = models.ForeignKey(
        'AnimalsWeightRanges',
        related_name='animals',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    animal_breed_groups = models.ForeignKey(
        'AnimalsBreedGroups',
        related_name='animals',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        db_table = "animals"
        ordering = ("-created_at",)
        indexes = [GinIndex(fields=['characteristic_board'])]

    def __str__(self) -> str:
        return self.name

    # wygodniczek
    @property
    def age(self) -> int | None:
        if self.birth_date:
            return (timezone.now().date() - self.birth_date).days // 365
        return None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])


# ────────────────────────────────────────────────────────────────────
#  Charakterystyki / cechy boolowskie
# ────────────────────────────────────────────────────────────────────
# 
class Characteristics(models.Model):
    id          = models.BigAutoField(primary_key=True)
    characteristic         = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True, null=True)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "characteristics"

    def __str__(self) -> str:
        return self.characteristic
    

class AnimalCharacteristic(models.Model):
    id          = models.BigAutoField(primary_key=True)
    animal      = models.ForeignKey(
        Animal, related_name="characteristics_values",
        on_delete=models.CASCADE
    )
    characteristics = models.ForeignKey(
        Characteristics,
        related_name='animal_characteristics_values',
        on_delete=models.CASCADE
    )
    value  = models.BooleanField()

    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table  = "animal_characteristics"
        unique_together = (("animal", "characteristics"),)

    def __str__(self) -> str:
        return f"{self.animal} {self.value}"
    



# ────────────────────────────────────────────────────────────────────
#  Galeria zdjęć
# ────────────────────────────────────────────────────────────────────
class AnimalGallery(models.Model):
    id          = models.BigAutoField(primary_key=True)
    animal      = models.ForeignKey(
        Animal, related_name="gallery",
        on_delete=models.CASCADE
    )
    image         = models.ImageField(
        upload_to="animals/gallery/",
        help_text="Zalecany rozmiar: 800x600px"
    )
    images   = ArrayField(
        models.ImageField(upload_to="animals/gallery/", blank=True, null=True),
        size=5,
        blank=True,
        null=True
    )
    #ordering    = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "animal_gallery"
        #ordering = ("ordering",)

    


# ────────────────────────────────────────────────────────────────────
#  Relacje rodzic-dziecko
# ────────────────────────────────────────────────────────────────────
class AnimalParent(models.Model):
    id          = models.BigAutoField(primary_key=True)
    animal      = models.ForeignKey(
        Animal,
        related_name="parentships",            # z perspektywy dziecka
        on_delete=models.CASCADE,
    )
    parent      = models.ForeignKey(
        Animal,
        related_name="offsprings",             # z perspektywy rodzica
        on_delete=models.CASCADE,
    )
    relation    = models.CharField(max_length=8, choices=ParentRelation.choices)

    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "animal_parents"
        unique_together = (("animal", "parent", "relation"),)

    def clean(self):
        super().clean()
        qs = self.__class__.objects.filter(animal=self.animal)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        # max two parents per animal
        if qs.count() >= 2:
            raise ValidationError("Zwierzę może mieć maksymalnie dwóch rodziców.")
        # only one mother or father per animal (guardians can be multiple)
        # only one parent of each relation (guardians allowed multiple)
        if self.relation in (ParentRelation.MOTHER, ParentRelation.FATHER):
            if qs.filter(relation=self.relation).exists():
                raise ValidationError(
                f"Zwierzę {self.animal} już ma relację {self.relation}."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.parent_id} -> {self.animal_id} ({self.relation})"
    


class AnimalsWeightRanges(models.Model):
    id = models.BigAutoField(primary_key=True)
    breed = models.CharField(max_length=100, unique=True)
    min_weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    max_weight = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    example_breeds = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)



    class Meta:
        db_table = "animal_weight_ranges"

    def __str__(self):
        return f"{self.breed}: {self.min_weight} - {self.max_weight} kg"
    

class AnimalsBreedGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    group_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    min_weight = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],
        null=True, blank=True,
        help_text="Average weight range for this group in kg"
    )

    max_weight = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],
        null=True, blank=True,
        help_text="Average weight range for this group in kg"
    )


    min_size_male = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],
        null=True, blank=True,
        help_text="Minimum size male"
    )
    max_size_male = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],\
        null=True, blank=True,
        help_text="Maximum size male"
    )

    min_size_famale = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],
        null=True, blank=True,
        help_text="Minimum size famale"
    )
    max_size_famale = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0)],
        null=True, blank=True,
        help_text="Maximum size famale"
    )

    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "animal_breed_groups"

    def __str__(self):
        return self.group_name