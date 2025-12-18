from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import Organization, Address, OrganizationMember
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, BreedingTypeOrganizations, Species, BreedingType

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):

    list_display = ("name", "type", "email", "description", "rating", "created_at", "image")
    search_fields = ("name", "email")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("organization", "city", "street", "zip_code", "lat", "lng", "location")
    filter_horizontal = ("species",)  # multi-pick


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "role", "joined_at")
    list_filter  = ("role",)



@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("email", "role", "is_active", "created_at")
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dane osobowe", {"fields": ("first_name", "last_name", "phone", "image")}),
        ("Uprawnienia", {"fields": ("role", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Daty", {"fields": ("created_at", "updated_at", "deleted_at")}),
        ("Geolokalizacja", {"fields": ("location",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "first_name", "last_name"),
        }),
    )





    

@admin.register(BreedingTypeOrganizations)
class OrganizationBreedingTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "organization", "breeding_type")


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    '''Admin panel dla gatunków zwierząt.'''
    list_display = ("id", "name", "description")
    search_fields = ("name",)

@admin.register(BreedingType)
class BreedingTypeAdmin(admin.ModelAdmin):
    '''Admin panel dla typów hodowli zwierząt.'''

    list_display = ("id", "name", "description")
    search_fields = ("name",)


    
