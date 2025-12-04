from rest_framework import serializers
from .models import User
from .models import Organization, Address, OrganizationMember, BreedingTypeOrganizations, \
      BreedingType, Species
from .models import OrganizationType

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
        from binascii import Error as BinasciiError
        from django.core.files.base import ContentFile

        if isinstance(data, str):
            # Accept both data URI notation ("data:image/png;base64,<...>")
            # and a raw base64 string without the prefix.
            if data.startswith("data:image"):
                try:
                    header, imgstr = data.split(";base64,", 1)
                except ValueError:
                    raise serializers.ValidationError("Niepoprawny format danych obrazu.")

                mime_part = header.split("/")[-1]
                try:
                    decoded = base64.b64decode(imgstr)
                except (BinasciiError, ValueError):
                    raise serializers.ValidationError("Nie można odczytać przesłanego obrazu (Base64).")

                ext = (mime_part.split(";")[0] or imghdr.what(None, decoded) or "png")
            else:
                try:
                    decoded = base64.b64decode(data)
                except (BinasciiError, ValueError):
                    raise serializers.ValidationError("Nie można odczytać przesłanego obrazu (Base64).")

                ext = imghdr.what(None, decoded) or "png"

            file_name = f"{uuid.uuid4()}.{ext}"
            data = ContentFile(decoded, name=file_name)

        return super().to_internal_value(data)
    

class UserSerializer(serializers.ModelSerializer):
    """Serializer do odczytu danych użytkownika."""
    full_name = serializers.CharField(read_only=True)
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "image",
            "phone",
            "role",
            "created_at",
            "updated_at",
            "deleted_at",
            "is_active",
            "is_staff",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer do tworzenia nowego użytkownika."""
    password = serializers.CharField(write_only=True, required=True)
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "image",
            "phone",
            #"role",
        ]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer do aktualizacji danych użytkownika."""
    password = serializers.CharField(write_only=True, required=False)
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "password",
            "image",
            "phone",
            "role",
            "is_active",
            "is_staff",
        ]

    def update(self, instance, validated_data):
        pwd = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if pwd:
            instance.set_password(pwd)
        instance.save()
        return instance
    


class AddressSerializer(serializers.ModelSerializer):
    """Serializer adresu organizacji."""
    distance = serializers.SerializerMethodField(read_only=True)
    species = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Species.objects.all()
    )
    class Meta:
        model = Address
        fields = [
            "city",
            "street",
            "house_number",
            "zip_code",
            "lat",
            "lng",
            "location",
            "distance",
            "species",
        ]
    def get_distance(self, obj):
        # Jeśli w queryset było .annotate(distance=...), to obj.distance to GEOSDistance
        dist = getattr(obj, "distance", None)
        if dist is None and hasattr(obj, "organization"):
            dist = getattr(obj.organization, "distance", None)
        return None if dist is None else round(dist.m)  # zwraca odległość w metrach
    
    
    


# class SpeciesOrganizationsSerializer(serializers.ModelSerializer):
#     """Serializer dla organizacji według gatunku."""
#     class Meta:
#         model = SpeciesOrganizations
#         fields = [
#             "id",
#             "organization",
#             "species",
#         ]
    
class BreedingTypeOrganizationsSerializer(serializers.ModelSerializer):
    """Serializer dla organizacji według typu hodowli."""
    class Meta:
        model = BreedingTypeOrganizations
        fields = [
            "id",
            "organization",
            "breeding_type",
        ]

class SpeciesSerializer(serializers.ModelSerializer):
    """Serializer gatunku zwierzęcia."""
    class Meta:
        model = Species
        fields = [
            "id",
            "name",
            "description",
        ]
class BreedingTypeSerializer(serializers.ModelSerializer):
    """Serializer typu hodowli zwierzęcia."""
    class Meta:
        model = BreedingType
        fields = [
            "id",
            "name",
            "description",
        ]

class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer odczytu organizacji wraz z adresem i powiązaniami."""
    address = AddressSerializer(required=True)
    image = Base64ImageField(required=False, allow_null=True)
    # species = SpeciesOrganizationsSerializer(
    #     source='speciesorganizations_set',
    #     many=True,
    #     required=True,
    # )
    # breeding_type = BreedingTypeOrganizationsSerializer(
    #     source='breedingtypeorganizations_set',
    #     many=True,
    #     required=True,
    # )

    class Meta:
        model = Organization
        fields = [
            "id",
            "type",
            "name",
            "email",
            "image",
            "phone",
            "description",
            "rating",
            "created_at",
            "updated_at",
            "deleted_at",
            "address",
            "user",
            
            # "species",
            # "breeding_type",
        ]
        read_only_fields = ('user',)      # <- nie przyjmujemy ownera z request body

    def create(self, validated_data):
        address_data = validated_data.pop("address")
        species = address_data.pop("species", [])
        org = Organization.objects.create(**validated_data)
        address = Address.objects.create(organization=org, **address_data)
        if species:
            address.species.set(species)
        return org

    def update(self, instance, validated_data):
        address_data = validated_data.pop("address", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if address_data is not None:
            species = address_data.pop("species", None)
            address = getattr(instance, "address", None)

            if address is None:
                address = Address.objects.create(organization=instance, **address_data)
            else:
                for attr, value in address_data.items():
                    setattr(address, attr, value)
                address.save()

            if species is not None:
                address.species.set(species)

        return instance


class OrganizationCreateSerializer(serializers.ModelSerializer):
    """Serializer tworzenia nowej organizacji wraz z adresem."""
    address = AddressSerializer()
    image = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Organization
        fields = [
            "type",
            "name",
            "email",
            "image",
            "phone",
            "description",
            "rating",
            "address",
        ]

    def create(self, validated_data):
        address_data = validated_data.pop("address")
        species = address_data.pop("species", [])
        org = Organization.objects.create(**validated_data)
        address = Address.objects.create(organization=org, **address_data)
        if species:
            address.species.set(species)
        return org


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    """Serializer aktualizacji organizacji."""
    image = Base64ImageField(required=False, allow_null=True)
    class Meta:
        model = Organization
        fields = [
            "type",
            "name",
            "email",
            "image",
            "phone",
            "description",
            "rating",
        ]

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class OrganizationMemberSerializer(serializers.ModelSerializer):
    """Serializer odczytu członkostwa."""
    user = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationMember
        fields = [
            "id",
            "user",
            "organization",
            "role",
            "joined_at",
            "updated_at",
            "deleted_at",
        ]


class OrganizationMemberCreateSerializer(serializers.ModelSerializer):
    """Serializer dodawania użytkownika do organizacji."""
    class Meta:
        model = OrganizationMember
        fields = [
            "user",
            "organization",
            "role",
        ]

    def create(self, validated_data):
        return OrganizationMember.objects.create(**validated_data)
    

class LatestOrganizationSerializer(serializers.ModelSerializer):
    """Serializer dla ostatnio dodanych organizacji."""
    address = AddressSerializer(read_only=True)
    members = OrganizationMemberSerializer(
        source='organizationmember_set',
        many=True,
        read_only=True
    )

    class Meta:
        model = Organization
        fields = [
            "id",
            "type",
            "name",
            "email",
            "image",
            "phone",
            "description",
            "rating",
            "created_at",
            "address",
            "members",
        ]
        # UWAGA: Kolejność zwracanych organizacji ustaw w widoku:
        # queryset = Organization.objects.order_by('-created_at')[:N]




class OrganizationTypeSerializer(serializers.Serializer):
    """Representation of organization type choices."""
    value = serializers.CharField()
    label = serializers.CharField()

    @staticmethod
    def get_choices():
        return [
            {"value": choice.value, "label": choice.label}
            for choice in OrganizationType
        ]