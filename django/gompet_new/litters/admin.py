from django.contrib import admin

from .models import Litter, LitterAnimal


# Register your models here.

@admin.register(Litter)
class LitterAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'description', 'status', 'owner',
        'organization', 'created_at', 'updated_at', 'deleted_at'
    )
    list_filter = ('status', 'owner', 'organization')
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'status')
        }),
        ('Ownership & Organization', {
            'fields': ('owner', 'organization')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )

@admin.register(LitterAnimal)
class LitterAnimalAdmin(admin.ModelAdmin):
    list_display = ('id', 'litter', 'animal', 'updated_at', 'deleted_at')
    search_fields = ('litter__title', 'animal__name')
    readonly_fields = ('updated_at', 'deleted_at')

    fieldsets = (
        (None, {
            'fields': ('litter', 'animal')
        }),
        ('Timestamps', {
            'fields': ('updated_at', 'deleted_at')
        }),
    )