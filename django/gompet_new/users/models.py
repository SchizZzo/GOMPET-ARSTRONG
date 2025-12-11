from django.db import models

# Create your models here.
# users/models.py
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.contrib.gis.db import models as gis_models



# ─────────────────────────────────────────────────────────────
# Gatunek / grupa zwierząt prowadzących organizację (schronisko, fundacja itd.)
# ─────────────────────────────────────────────────────────────
class OrganizationSpecies(models.TextChoices):
    DOG        = "dog",        "Dog"
    CAT        = "cat",        "Cat"
    RABBIT     = "rabbit",     "Rabbit"
    GUINEA_PIG = "guinea_pig", "Guinea pig"
    HAMSTER    = "hamster",    "Hamster"
    RAT        = "rat",        "Rat"
    MOUSE      = "mouse",      "Mouse"
    BIRD       = "bird",       "Bird"
    REPTILE    = "reptile",    "Reptile"
    AMPHIBIAN  = "amphibian",  "Amphibian"
    FISH       = "fish",       "Fish"
    OTHER      = "other",      "Other"


# ─────────────────────────────────────────────────────────────
# Typ hodowli / profilu działalności organizacji
# ─────────────────────────────────────────────────────────────
class OrganizationBreedingType(models.TextChoices):
    PET          = "pet",          "Towarzyska / domowa"
    POULTRY      = "poultry",      "Drobiu"
    CATTLE       = "cattle",       "Bydło"
    SWINE        = "swine",        "Trzoda chlewna"
    FUR          = "fur",          "Futerkowa"
    AQUACULTURE  = "aquaculture",  "Akwakultura"
    APICULTURE   = "apiculture",   "Pszczelarstwo"
    LABORATORY   = "laboratory",   "Laboratoryjna"
    CONSERVATION = "conservation", "Konserwatorska"
    OTHER        = "other",        "Inna"




class UserRole(models.TextChoices):
    SUPERADMIN = "SUPERADMIN", "Super Admin"
    ADMIN      = "ADMIN",      "Admin"
    STAFF      = "STAFF",      "Staff"
    USER       = "USER",       "User"


phone_validator = RegexValidator(
    regex=r"^\+?[0-9 ]+$",
    message="Dozwolone cyfry, spacje i opcjonalny znak + na początku.",
)


class UserManager(BaseUserManager):
    """Custom manager z użyciem e-maila jako loginu."""

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Użytkownik musi mieć adres e-mail")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("role", UserRole.USER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("role", UserRole.SUPERADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Główny model użytkownika zgodny z Twoim ERD."""

    id          = models.BigAutoField(primary_key=True)
    email       = models.EmailField(unique=True)
    image       = models.ImageField(
        upload_to="users/images/",
        blank=True,
        null=True,
    )
    first_name  = models.CharField(max_length=150)
    last_name   = models.CharField(max_length=150, blank=True, default="")
    phone       = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    role        = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.USER)

    location    = gis_models.PointField(null=True, blank=True, geography=True)  # możesz zamienić na ForeignKey→Address

    

    # pola audytu
    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)
    is_deleted  = models.BooleanField(default=False)

    # Django-owe flagi
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)  # dostęp do admina

    objects     = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name"]

    class Meta:
        db_table = "users"
        verbose_name = "Użytkownik"
        verbose_name_plural = "Użytkownicy"
        ordering = ("-created_at",)

    # ───────────────  helpery  ───────────────
    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def soft_delete(self):
        """Oznacza użytkownika jako usuniętego bez fizycznego kasowania."""
        self.deleted_at = timezone.now()
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["deleted_at", "is_active", "is_deleted"])


# organizations/models.py
from django.conf import settings
from django.core.validators import (
    RegexValidator,
    MinValueValidator,
    MaxValueValidator,
)
from django.db import models
from django.utils import timezone


# ────────────────────────────────────────────────────────────────────
#  Enum-y / walidatory
# ────────────────────────────────────────────────────────────────────
phone_validator = RegexValidator(
    regex=r"^\+?[0-9 ]+$",
    message="Dozwolone cyfry, spacje i opcjonalny znak + na początku.",
)


class OrganizationType(models.TextChoices):
    SHELTER = "SHELTER", "Schronisko"
    FUND  = "FUND",   "Fundacja"
    BREEDER = "BREEDER", "Hodowla"
    CLINIC  = "CLINIC",  "Gabinet weterynaryjny"
    SHOP    = "SHOP",    "Sklep zoologiczny"
    OTHER   = "OTHER",   "Inne"


class MemberRole(models.TextChoices):
    OWNER   = "OWNER",   "Właściciel / Kierownik"
    STAFF   = "STAFF",   "Pracownik"
    VOLUNTEER = "VOLUNTEER", "Wolontariusz"


# ────────────────────────────────────────────────────────────────────
#  Modele
# ────────────────────────────────────────────────────────────────────
class Organization(models.Model):
    """
    Główna tabela `organizations` – odpowiada pola z ERD.
    """

    id          = models.BigAutoField(primary_key=True)
    type        = models.CharField(max_length=20, choices=OrganizationType.choices)
    name        = models.CharField(max_length=255, unique=True)
    email       = models.EmailField(unique=True)
    image       = models.ImageField(
        upload_to="organizations/images/",
        blank=True,
    )                      # lub ImageField(...)
    phone       = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    description = models.JSONField(blank=True, null=True, help_text="Opis organizacji w formacie JSON.")
    rating      = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="organizations",
        
        help_text="Opcjonalny właściciel organizacji (użytkownik)."
    )

    

    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)
    deleted_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "organizations"
        ordering = ("-created_at",)

    def __str__(self) -> str:      # czytelne w adminie / shellu
        return self.name
    
    

    # Soft-delete helper
    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])





class OrganizationMember(models.Model):
    """
    Tabela łącznikowa user ↔ organization
    (unique razem = nie można dwa razy dodać tego samego członka).
    """

    id             = models.BigAutoField(primary_key=True)
    user           = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization   = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )
    role           = models.CharField(
        max_length=20,
        choices=MemberRole.choices,
        default=MemberRole.STAFF,
    )
    joined_at      = models.DateTimeField(default=timezone.now)

    updated_at     = models.DateTimeField(auto_now=True)
    deleted_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table   = "organization_members"
        ordering   = ("-joined_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"), name="uniq_user_org"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.full_name} @ {self.organization.name}"



# class SpeciesOrganizations(models.Model):
#     """
#     Tabela łącznikowa organizacja ↔ gatunki zwierząt.
#     """
#     id             = models.BigAutoField(primary_key=True)
#     organization   = models.ForeignKey(
#         Organization,
#         on_delete=models.CASCADE,
#         related_name="species_organizations",
#     )
    
#     species = models.ForeignKey(
#         "Species",
#         on_delete=models.CASCADE,
#         related_name="organizations",
#     )

#     class Meta:
#         db_table   = "species_organizations"
#         unique_together = (("organization", "species"),)

#     def __str__(self) -> str:
#         return f"{self.organization.name} - {self.species}"
    

class BreedingTypeOrganizations(models.Model):
    """
    Tabela łącznikowa organizacja ↔ typ hodowli.
    """
    id             = models.BigAutoField(primary_key=True)
    organization   = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="breeding_type_organizations",
    )
    breeding_type  = models.ForeignKey(
        "BreedingType",
        on_delete=models.CASCADE,
        related_name="organizations",
    )

    class Meta:
        db_table   = "breeding_type_organizations"
        unique_together = (("organization", "breeding_type"),)

    def __str__(self) -> str:
        return f"{self.organization.name} - {self.breeding_type}"
    

class Species(models.Model):
    """
    Model gatunku zwierzęcia.
    """
    id             = models.BigAutoField(primary_key=True)
    name           = models.CharField(max_length=100, unique=True)
    description    = models.TextField(blank=True, null=True)

    created_at     = models.DateTimeField(default=timezone.now)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "species"

    def __str__(self) -> str:
        return self.name
    
class BreedingType(models.Model):
    """
    Model typu hodowli.
    """
    id             = models.BigAutoField(primary_key=True)
    name           = models.CharField(max_length=100, unique=True)
    description    = models.TextField(blank=True, null=True)

    created_at     = models.DateTimeField(default=timezone.now)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "breeding_types"

    def __str__(self) -> str:
        return self.name
    

class Address(models.Model):
    """
    Jedno-do-jednego z Organization (możesz łatwo zmienić na ManyToOne
    – wtedy usuń `unique=True` w FK).
    """

    id             = models.BigAutoField(primary_key=True)
    organization   = models.OneToOneField(
        Organization,
        related_name="address",
        on_delete=models.CASCADE,
        unique=True,
    )

    species = models.ManyToManyField(Species, related_name="organizations", blank=True)

    city           = models.CharField(max_length=120)
    street         = models.CharField(max_length=120)
    house_number   = models.CharField(max_length=10)
    zip_code       = models.CharField(max_length=12)
    lat            = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng            = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location    = gis_models.PointField(null=True, blank=True, geography=True)


    updated_at     = models.DateTimeField(auto_now=True)
    deleted_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "addresses"

    def __str__(self) -> str:
        return f"{self.street} {self.house_number}, {self.city}"