from rest_framework import serializers

from .models import (
    Animal,
    AnimalCharacteristic,
    AnimalGallery,
    AnimalParent,
    Characteristics,
    AnimalsBreedGroups,
)
from django.contrib.gis.measure import Distance as D
from django.contrib.gis.db.models.functions import Distance

from users.serializers import OrganizationSerializer


class Base64ImageField(serializers.ImageField):
    """
    Przyjmuje data URI lub czysty base‑64 i konwertuje na ContentFile.
    """
    def to_internal_value(self, data):
        import base64, imghdr, uuid
        from django.core.files.base import ContentFile

        if isinstance(data, str) and data.startswith("data:image"):
            fmt, imgstr = data.split(";base64,")
            ext = imghdr.what(None, base64.b64decode(imgstr))
            file_name = f"{uuid.uuid4()}.{ext}"
            data = ContentFile(base64.b64decode(imgstr), name=file_name)
        return super().to_internal_value(data)


class CharacteristicsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Characteristics
        fields = ('id', 'characteristic', 'description', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

class AnimalCharacteristicSerializer(serializers.ModelSerializer):
    
    
    
   
    class Meta:
        model = AnimalCharacteristic
        fields = (
            'id',
            'characteristics',
            'value',
            
        )


class AnimalGallerySerializer(serializers.ModelSerializer):
    image = Base64ImageField(required=False, allow_null=True)
    images = serializers.ListField(
        child=Base64ImageField(), write_only=True, required=False
    )
    animal = serializers.PrimaryKeyRelatedField(
        queryset=Animal.objects.all(), write_only=True, required=False
    )

    class Meta:
        model = AnimalGallery
        fields = (
            "id",
            "image",
            "images",
            "animal",
            #"ordering",
        )

    def create(self, validated_data):
        images = validated_data.pop("images", None)
        animal = validated_data.pop("animal", None)
        if images:
            if animal is None:
                raise serializers.ValidationError(
                    {"animal": "This field is required when uploading multiple images."}
                )
            instances = [
                AnimalGallery(animal=animal, image=image) for image in images
            ]
            AnimalGallery.objects.bulk_create(instances)
            return instances[0]
        if animal is not None:
            validated_data["animal"] = animal
        return super().create(validated_data)


class AnimalParentSerializer(serializers.ModelSerializer):
    # both sides: `parent` if used under `parentships`, `animal` if under `offsprings`
    parent = serializers.PrimaryKeyRelatedField(read_only=True)
    animal = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = AnimalParent
        fields = (
            "id",
            "parent",
            "animal",
            "relation",
        )


class GrandparentSerializer(serializers.ModelSerializer):
    """Serialize a grandparent relationship for a given parent."""

    id = serializers.IntegerField(source="parent.id", read_only=True)
    name = serializers.CharField(source="parent.name", read_only=True)
    photos = serializers.SerializerMethodField()
    parentsOfWho = serializers.CharField(
        source="get_relation_display", read_only=True
    )

    class Meta:
        model = AnimalParent
        fields = ("id", "name", "photos", "parentsOfWho")

    def get_photos(self, obj):
        image = getattr(obj.parent, "image", None)
        if not image:
            return None
        request = self.context.get("request") if hasattr(self, 'context') else None
        url = image.url
        return request.build_absolute_uri(url) if request else url


class ParentWithGrandparentsSerializer(serializers.ModelSerializer):
    """Serialize a parent along with its own parents (grandparents)."""

    id = serializers.IntegerField(source="parent.id", read_only=True)
    name = serializers.CharField(source="parent.name", read_only=True)
    gender = serializers.CharField(source="parent.gender", read_only=True)
    photos = serializers.SerializerMethodField()
    grandparents = serializers.SerializerMethodField()

    class Meta:
        model = AnimalParent
        fields = ("id", "name", "gender", "photos", "grandparents")

    def get_photos(self, obj):
        image = getattr(obj.parent, "image", None)
        if not image:
            return None
        request = self.context.get("request") if hasattr(self, 'context') else None
        url = image.url
        return request.build_absolute_uri(url) if request else url

    def get_grandparents(self, obj):
        qs = AnimalParent.objects.filter(animal=obj.parent)
        serializer = GrandparentSerializer(qs, many=True, context=self.context)
        return serializer.data
    
class CharacterItemSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=64)
    bool = serializers.BooleanField()


class AnimalSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    # use the correct related name to retrieve characteristic values
    # characteristics = AnimalCharacteristicSerializer(
    #     source="characteristics_values", many=True, read_only=True
    # )
    gallery = AnimalGallerySerializer(many=True, required=True)
    parents = serializers.SerializerMethodField(read_only=True)
    parentships = AnimalParentSerializer(many=True, read_only=True)
    offsprings = AnimalParentSerializer(many=True, read_only=True)
    comments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    distance = serializers.SerializerMethodField(read_only=True)
    organization = serializers.SerializerMethodField(read_only=True)

    characteristicBoard = CharacterItemSerializer(many=True, source='characteristic_board')

    image = Base64ImageField(required=False, allow_null=True)



    
    class Meta:
        model = Animal
        fields = (
            "id",
            "name",
            "image",
            "descriptions",
            "species",
            "breed",
            "gender",
            "size",
            "birth_date",
            "owner",
            "status",
            "price",
            "city",
            "location",
            "parents",
            "distance",
            "age",
            "characteristicBoard",
            "gallery",
            "parentships",
            "offsprings",
            "comments",
            "reactions",
            "organization",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
        )
    def get_distance(self, obj):
        # Jeśli w queryset było .annotate(distance=...), to obj.distance to GEOSDistance
        dist = getattr(obj, "distance", None)
        return None if dist is None else round(dist.m)  # zwraca odległość w metrach
    
    def get_organization(self, obj):
        """Return organization data via owner memberships."""
        user = getattr(obj, "owner", None)
        if not user:
            return None
        membership = user.memberships.first()
        if not membership:
            return None
        return OrganizationSerializer(membership.organization).data

    def get_parents(self, obj):
        qs = AnimalParent.objects.filter(animal=obj)
        serializer = ParentWithGrandparentsSerializer(qs, many=True, context=self.context)
        return serializer.data

    def create(self, validated_data):
        gallery_data = validated_data.pop("gallery", [])
        animal = super().create(validated_data)
        for image_data in gallery_data:
            AnimalGallery.objects.create(animal=animal, **image_data)
        return animal

    def update(self, instance, validated_data):
        gallery_data = validated_data.pop("gallery", None)
        animal = super().update(instance, validated_data)
        if gallery_data is not None:
            instance.gallery.all().delete()
            for image_data in gallery_data:
                AnimalGallery.objects.create(animal=animal, **image_data)
        return animal
    
    

class AnimalParentTreeSerializer(serializers.ModelSerializer):
    class AnimalParentTreeSerializer(serializers.ModelSerializer):
        MAX_DEPTH = 3

        animal = AnimalSerializer(read_only=True)
        parent = AnimalSerializer(read_only=True)
        image = serializers.ImageField(source='animal.image', read_only=True)
        relation = serializers.CharField(source='get_relation_display', read_only=True)
        parents = serializers.SerializerMethodField()
        offsprings = serializers.SerializerMethodField()

        class Meta:
            model = AnimalParent
            fields = (
                "animal",
                "parent",
                "relation",
                "parents",
                "offsprings",
                "image",
            )
            read_only_fields = ("relation",)

        def __init__(self, *args, **kwargs):
            self.depth = kwargs.get('context', {}).get('depth', 0)
            super().__init__(*args, **kwargs)

        def get_parents(self, obj):
            if self.depth >= self.MAX_DEPTH:
                return []
            qs = AnimalParent.objects.filter(animal=obj.parent)
            serializer = AnimalParentTreeSerializer(
                qs,
                many=True,
                context={'depth': self.depth + 1}
            )
            return serializer.data

        def get_offsprings(self, obj):
            if self.depth >= self.MAX_DEPTH:
                return []
            qs = AnimalParent.objects.filter(parent=obj.animal)
            serializer = AnimalParentTreeSerializer(
                qs,
                many=True,
                context={'depth': self.depth + 1}
            )
            return serializer.data


    # def get_offsprings(self, obj):
    #     if self.depth >= self.MAX_DEPTH:
    #         return []
    #     qs = AnimalParent.objects.filter(parent=obj.animal)
    #     serializer = AnimalParentTreeSerializer(
    #         qs,
    #         many=True,
    #         context={'depth': self.depth + 1}
    #     )
    #     return serializer.data
    

    



class RecentlyAddedAnimalSerializer(serializers.ModelSerializer):
    """
    Serializer for listing recently added animals with minimal fields.
    """
    
    characteristics = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField(read_only=True)

    def get_characteristics(self, obj):
        return [
            {   "id": ac.id,
                "name": ac.characteristics.characteristic,
                "value": ac.value,
            }
            for ac in obj.characteristics_values.all()
        ]
    def get_distance(self, obj):
        # Jeśli w queryset było .annotate(distance=...), to obj.distance to GEOSDistance
        dist = getattr(obj, "distance", None)
        return None if dist is None else round(dist.m)  # zwraca odległość w metrach
    class Meta:
        model = Animal
        fields = (
            "id",
            "name",
            "species",
            "characteristics",
            "age",
            "city",
            
            "breed",
            "image",
            "location",
            "distance",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class AnimalsBreedGroupsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnimalsBreedGroups
        fields = ('id', 'group_name', 'description', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    




            
        

    

