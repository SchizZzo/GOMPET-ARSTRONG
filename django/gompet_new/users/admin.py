from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Address,
    BreedingType,
    BreedingTypeOrganizations,
    Organization,
    OrganizationMember,
    Species,
    User,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "type",
        "user",
        "email",
        "description",
        "rating",
        "created_at",
        "image",
    )
    search_fields = ("name", "email")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("organization", "city", "street", "zip_code", "lat", "lng", "location")
    filter_horizontal = ("species",)


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "organization", "role", "joined_at")
    list_filter = ("role",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("id", "email", "location", "role", "is_active", "created_at")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dane osobowe", {"fields": ("first_name", "last_name", "phone", "image")}),
        (
            "Uprawnienia",
            {"fields": ("role", "is_active", "is_superuser", "groups", "user_permissions")},
        ),
        ("Daty", {"fields": ("created_at", "updated_at", "deleted_at")}),
        ("Geolokalizacja", {"fields": ("location",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "first_name", "last_name"),
            },
        ),
    )


@admin.register(BreedingTypeOrganizations)
class OrganizationBreedingTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "breeding_type")


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "label", "description")
    search_fields = ("name", "label")


@admin.register(BreedingType)
class BreedingTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description")
    search_fields = ("name",)
