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

from users.models import Species, Organization

from datetime import date

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

class AgeCategory(models.TextChoices):
    PUPPY_JUNIOR = "PUPPY_JUNIOR", "Puppy/Junior"
    ADULT        = "ADULT",        "Adult"
    SENIOR       = "SENIOR",       "Senior"


class LifePeriod(models.TextChoices):
    PUPPY = "PUPPY", "Puppy"
    ADULT = "ADULT", "Adult"
    SENIOR = "SENIOR", "Senior"


# ────────────────────────────────────────────────────────────────────
#  Core Animal model
# ────────────────────────────────────────────────────────────────────
class Animal(models.Model):


    def validate_birth_date(value):
        if value > timezone.now().date():
            raise ValidationError("Zwierzę nie może mieć daty urodzenia w przyszłości.")
        

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
    

    birth_date  = models.DateField(
        null=True,
        blank=True,
        validators=[validate_birth_date],
    )

    # właściciel (np. użytkownik lub organizacja – tutaj user)
    owner       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="animals",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        Organization,
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


    age = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Wiek w latach"
    )

    life_period = models.CharField(
        max_length=50,
        choices=LifePeriod.choices,
        default=LifePeriod.PUPPY
    )

    class Meta:
        db_table = "animals"
        ordering = ("-created_at",)
        indexes = [GinIndex(fields=['characteristic_board'])]

    def save(self, *args, **kwargs):
        if self.location is None and self.owner:
            owner_location = getattr(self.owner, "location", None)
            if owner_location is not None:
                self.location = owner_location
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
    
    

    

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def save(self, *args, **kwargs):
        """Calculate age from birth_date before saving."""
        if self.birth_date:
            today = timezone.now().date()
            self.age = today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        else:
            self.age = None
        super().save(*args, **kwargs)

    @property
    def age_display(self) -> str:
        if not self.birth_date:
            return "brak danych"

        birth_date = self.birth_date
        today = date.today()

        years = today.year - birth_date.year
        months = today.month - birth_date.month
        days = today.day - birth_date.day

        # Adjust when days or months are negative
        if days < 0:
            months -= 1
        if months < 0:
            years -= 1
            months += 12

        result = []
        if years > 0:
            result.append(
                f"{years} rok"
                if years == 1
                else f"{years} lata" if 2 <= years <= 4 else f"{years} lat"
            )
        if months > 0:
            result.append(
                f"{months} miesiąc"
                if months == 1
                else f"{months} miesiące" if 2 <= months <= 4 else f"{months} miesięcy"
            )

        return " ".join(result) if result else "mniej niż miesiąc"


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
        if self.parent.gender == Gender.FEMALE:
            expected_relation = ParentRelation.MOTHER
        elif self.parent.gender == Gender.MALE:
            expected_relation = ParentRelation.FATHER
        else:
            raise ValidationError(
                "Rodzic musi mieć płeć MALE lub FEMALE, aby określić relację."
            )
        if self.relation != expected_relation:
            raise ValidationError(
                f"Relacja '{self.relation}' nie pasuje do płci rodzica '{self.parent.gender}'."
            )
        if self.parent.birth_date and self.animal.birth_date:
            if self.parent.birth_date >= self.animal.birth_date:
                raise ValidationError(
                    "Rodzic musi być starszy od zwierzęcia."
                )
        qs = self.__class__.objects.filter(animal=self.animal)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.count() >= 2:
            raise ValidationError("Zwierzę może mieć maksymalnie dwóch rodziców.")
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
    species = models.ForeignKey(
        Species,
        on_delete=models.CASCADE,
        related_name="breed_groups"
    )
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
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        help_text="Maximum size male",
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
