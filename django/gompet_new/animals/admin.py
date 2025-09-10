from django.contrib import admin
from .models import Animal, AnimalCharacteristic, AnimalGallery, AnimalParent, Characteristics, AnimalsBreedGroups

# Register your models here.
class AnimalCharacteristicInline(admin.TabularInline):
    model = AnimalCharacteristic
    extra = 1

class AnimalGalleryInline(admin.TabularInline):
    model = AnimalGallery
    extra = 1

class AnimalParentInline(admin.TabularInline):
    model = AnimalParent
    fk_name = 'animal'
    extra = 1



@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'species', 'breed', 'gender',
        'size', 'status', 'owner', 'price', 'location', 'city',
        'created_at',
    )
    list_filter = ('species', 'status', 'gender', 'size', 'owner')
    search_fields = ('name', 'breed', 'location', 'owner__username')
    readonly_fields = ('age', 'created_at', 'updated_at', 'deleted_at')
    inlines = [AnimalCharacteristicInline, AnimalGalleryInline, AnimalParentInline]
    fieldsets = (
        (None, {
            'fields': (
                'name', 'image', 'species', 'breed',
                'gender', 'size', 'birth_date', 'age',
                'animal_breed_groups',
            )
        }),
        ('Ownership & Status', {
            'fields': ('owner', 'status', 'price', 'location', 'city')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )


@admin.register(AnimalParent)
class AnimalParentAdmin(admin.ModelAdmin):
    list_display = ('id', 'animal', 'parent')
    search_fields = ('animal__name', 'parent__name')
    raw_id_fields = ('animal', 'parent')


@admin.register(AnimalCharacteristic)
class AnimalCharacteristicAdmin(admin.ModelAdmin):  
    list_display = ('id', 'animal', 'characteristics', 'value')
    search_fields = ('animal__name', 'characteristics__characteristic')
    list_filter = ('characteristics',)
    readonly_fields = ('updated_at', 'deleted_at')

@admin.register(Characteristics)
class CharacteristicsAdmin(admin.ModelAdmin):
    list_display = ('id', 'characteristic', 'description', 'created_at', 'updated_at')
    search_fields = ('characteristic',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')


@admin.register(AnimalsBreedGroups)
class AnimalsBreedGroupsAdmin(admin.ModelAdmin):
    list_display = ('id', 'group_name', 'description', 'created_at', 'updated_at')
    search_fields = ('group_name',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')

@admin.register(AnimalGallery)
class AnimalGalleryAdmin(admin.ModelAdmin):
    list_display = ('id', 'animal', 'image', 'created_at', 'updated_at')
    search_fields = ('animal__name',)
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')