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
    class Meta:
        model = AnimalGallery
        fields = (
            "id",
            "image",
            "ordering",
        )


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


<<<<<<< HEAD
=======
class GrandparentSerializer(serializers.ModelSerializer):
    """Serialize a grandparent relationship for a given parent."""

    name = serializers.CharField(source="parent.name", read_only=True)
    photos = serializers.SerializerMethodField()
    parentsOfWho = serializers.CharField(
        source="get_relation_display", read_only=True
    )

    class Meta:
        model = AnimalParent
        fields = ("name", "photos", "parentsOfWho")

    def get_photos(self, obj):
        image = getattr(obj.parent, "image", None)
        return image.url if image else None


class ParentWithGrandparentsSerializer(serializers.ModelSerializer):
    """Serialize a parent along with its own parents (grandparents)."""

    name = serializers.CharField(source="parent.name", read_only=True)
    gender = serializers.CharField(source="parent.gender", read_only=True)
    photos = serializers.SerializerMethodField()
    grandparents = serializers.SerializerMethodField()

    class Meta:
        model = AnimalParent
        fields = ("name", "gender", "photos", "grandparents")

    def get_photos(self, obj):
        image = getattr(obj.parent, "image", None)
        return image.url if image else None

    def get_grandparents(self, obj):
        qs = AnimalParent.objects.filter(animal=obj.parent)
        serializer = GrandparentSerializer(qs, many=True)
        return serializer.data
>>>>>>> 8684526b945908d82df16335ff512bb947b2d8c1


class AnimalSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    # use the correct related name to retrieve characteristic values
    characteristics = AnimalCharacteristicSerializer(
        source="characteristics_values", many=True, read_only=True
    )
    gallery = AnimalGallerySerializer(many=True, read_only=True)
    parents = serializers.SerializerMethodField(read_only=True)
    parentships = AnimalParentSerializer(many=True, read_only=True)
    offsprings = AnimalParentSerializer(many=True, read_only=True)
    comments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    distance = serializers.SerializerMethodField(read_only=True)


    organization = serializers.SerializerMethodField(read_only=True)
    



    parents = AnimalParentSerializer(many=True, read_only=True)


    
    class Meta:
        model = Animal
        fields = (
            "id", #ok 
            "name", #ok
            "image", #ok
            "species", #ok
            "breed", #ok
            "gender", #ok
            "size", #ok
            "birth_date", #ok
            "owner", 
            "status", #ok
            "price", #ok
            "city", #ok
            "location", #ok
            "parents", #ok



            "distance",
            "age",
            "characteristics",
            "gallery",
            "parents",
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
        serializer = ParentWithGrandparentsSerializer(qs, many=True)
        return serializer.data
    
    

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

    




            
        

    

