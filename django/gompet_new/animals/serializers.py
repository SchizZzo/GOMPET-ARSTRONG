from rest_framework import serializers

from .models import (
    Animal,
    AnimalCharacteristic,
    AnimalGallery,
    AnimalParent,
    Characteristics,
    AnimalsBreedGroups,
    Size,
)
from django.contrib.gis.measure import Distance as D
from django.contrib.gis.db.models.functions import Distance

from users.models import Organization, OrganizationMember
from users.serializers import OrganizationSerializer

from .models import ParentRelation

from common.serializers import CommentSerializer


class Base64ImageField(serializers.ImageField):
    """Accept a base64 string and convert it into an uploaded image.

    The field supports both plain base64 strings and ``data:image/...`` URIs.
    In both cases the decoded content is wrapped in a ``ContentFile`` so Django
    treats it like a regular uploaded file.
    """

    def to_internal_value(self, data):
        import base64
        import imghdr
        import uuid
        from django.core.files.base import ContentFile

        if isinstance(data, str):
            if data.startswith("data:image"):
                fmt, imgstr = data.split(";base64,")
                ext = imghdr.what(None, base64.b64decode(imgstr))
                file_name = f"{uuid.uuid4()}.{ext}"
                data = ContentFile(base64.b64decode(imgstr), name=file_name)
            else:
                ext = imghdr.what(None, base64.b64decode(data)) or "png"
                file_name = f"{uuid.uuid4()}.{ext}"
                data = ContentFile(base64.b64decode(data), name=file_name)
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
    """Simple serializer for gallery images.

    Only the ``image`` field is required when creating gallery items – the
    associated ``Animal`` instance is supplied by ``AnimalSerializer`` during
    creation.  The ``id`` field is read‑only and returned only in responses.
    """

    image = Base64ImageField()

    class Meta:
        model = AnimalGallery
        fields = ("id", "image")
        read_only_fields = ("id",)

   


class AnimalParentSerializer(serializers.ModelSerializer):
    # both sides: `parent` if used under `parentships`, `animal` if under `offsprings`
    parent = serializers.PrimaryKeyRelatedField(queryset=Animal.objects.all())
    animal = serializers.PrimaryKeyRelatedField(queryset=Animal.objects.all())
    relation = serializers.ChoiceField(choices=ParentRelation.choices)
    animal_id = serializers.IntegerField(source="animal.id", read_only=True)

    class Meta:
        model = AnimalParent
        fields = (
            "id",
            "animal_id",
            "parent",
            "animal",
            "relation",
        )


class GrandparentSerializer(serializers.ModelSerializer):
    """Serialize a grandparent relationship for a given parent."""

    animal_id = serializers.IntegerField(source="parent.id", read_only=True)
    name = serializers.CharField(source="parent.name", read_only=True)
    photos = serializers.SerializerMethodField()
    parentsOfWho = serializers.CharField(
        source="get_relation_display", read_only=True
    )

    

    class Meta:
        model = AnimalParent
        fields = ("id", "animal_id", "name", "photos", "parentsOfWho")

    def get_photos(self, obj):
        image = getattr(obj.parent, "image", None)
        if not image:
            return None
        request = self.context.get("request") if hasattr(self, 'context') else None
        url = image.url
        return request.build_absolute_uri(url) if request else url


class ParentWithGrandparentsSerializer(serializers.ModelSerializer):
    """Serialize a parent along with its own parents (grandparents)."""

    animal_id = serializers.IntegerField(source="parent.id", read_only=True)
    name = serializers.CharField(source="parent.name", read_only=True)
    gender = serializers.CharField(source="parent.gender", read_only=True)
    photos = serializers.SerializerMethodField()
    grandparents = serializers.SerializerMethodField()

    class Meta:
        model = AnimalParent
        fields = ("id", "animal_id", "name", "gender", "photos", "grandparents")

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
    image = Base64ImageField(required=False, allow_null=True)
    # use the correct related name to retrieve characteristic values
    # characteristics = AnimalCharacteristicSerializer(
    #     source="characteristics_values", many=True, read_only=True
    # )
    # Allow creating an animal without an initial gallery.  Tests only require
    # that provided gallery items are processed correctly, so the field should
    # be optional during validation.
    gallery = AnimalGallerySerializer(many=True, required=False)
    parents = serializers.SerializerMethodField(read_only=True)
    #parentships = AnimalParentSerializer(many=True, read_only=True)
    #offsprings = AnimalParentSerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    distance = serializers.SerializerMethodField(read_only=True)
    organization = serializers.SerializerMethodField(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        source="organization",
        queryset=Organization.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    # ``characteristicBoard`` is a JSON field on the model with a default value,
    # therefore it should not be required when creating an animal via the API.
    characteristicBoard = CharacterItemSerializer(
        many=True, source='characteristic_board', required=False
    )

    size = serializers.ChoiceField(choices=Size.choices)
    age_display = serializers.SerializerMethodField()
   

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
            "age_display",
            
            "life_period",
            "characteristicBoard",
            "gallery",
            #"parentships",
            #"offsprings",
            
           
            "comments",
            "reactions",
            "organization",
            "organization_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
        )

    
    def get_age_display(self, obj):
        return obj.age_display
    
    
    def get_distance(self, obj):
        # Jeśli w queryset było .annotate(distance=...), to obj.distance to GEOSDistance
        dist = getattr(obj, "distance", None)
        return None if dist is None else round(dist.m)  # zwraca odległość w metrach
    
    def get_organization(self, obj):
        """Return organization data via explicit relation or owner membership."""
        organization = getattr(obj, "organization", None)
        if organization:
            return OrganizationSerializer(organization).data
        user = getattr(obj, "owner", None)
        if not user:
            return None
        membership = user.memberships.first()
        if not membership:
            return None
        return OrganizationSerializer(membership.organization).data

    def validate_organization_id(self, organization):
        if organization is None:
            return organization
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Musisz być zalogowany, aby przypisać organizację."
            )
        is_member = OrganizationMember.objects.filter(
            user=request.user,
            organization=organization,
        ).exists()
        if not is_member:
            raise serializers.ValidationError(
                "Nie należysz do wskazanej organizacji."
            )
        return organization

    def get_parents(self, obj):
        qs = AnimalParent.objects.filter(animal=obj)
        serializer = ParentWithGrandparentsSerializer(qs, many=True, context=self.context)
        return serializer.data

    def validate_gallery(self, value):
        """Ensure every provided gallery item includes an image.

        The ``gallery`` field is optional, but if it is supplied we expect
        each nested item to contain an ``image``.  Without this check the
        serializer could quietly accept empty objects, later failing during
        ``AnimalGallery`` creation or producing unclear responses.  Raising a
        validation error here results in a clean ``400`` response that lists
        the offending entries.
        """

        missing = []
        for item in value:
            if not item.get("image"):
                missing.append({"image": ["No file was submitted."]})
        if missing:
            raise serializers.ValidationError(missing)
        return value

    def create(self, validated_data):
        gallery = validated_data.pop("gallery", [])
        animal = super().create(validated_data)
        for i, item in enumerate(gallery):
            AnimalGallery.objects.create(
                animal=animal,
                image=item.get("image"),
                
            )
        return animal

    def update(self, instance, validated_data):
        gallery = validated_data.pop("gallery", None)
        animal = super().update(instance, validated_data)
        if gallery is not None:
            instance.gallery.all().delete()
            for i, item in enumerate(gallery):
                AnimalGallery.objects.create(
                    animal=animal,
                    image=item.get("image"),
                    
                )
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
    
    #characteristics = serializers.SerializerMethodField()

    characteristicBoard = CharacterItemSerializer(
        many=True, source='characteristic_board', required=False
    )
    gender = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)


    size = serializers.CharField(read_only=True)

    distance = serializers.SerializerMethodField(read_only=True)

    

    # def get_characteristics(self, obj):
    #     return [
    #         {   "id": ac.id,
    #             "name": ac.characteristics.characteristic,
    #             "value": ac.value,
    #         }
    #         for ac in obj.characteristics_values.all()
    #     ]
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
            "characteristicBoard",
            "age",
            "city",
            "gender",
            "size",
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
        fields = ('id', 'group_name', 'species', 'description', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

    




            
        

    
