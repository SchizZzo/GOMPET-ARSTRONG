import base64
import binascii
import imghdr
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

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
        if isinstance(data, str):
            # Strip the header from data URI inputs
            if data.startswith("data:image"):
                try:
                    _, data = data.split(";base64,", 1)
                except ValueError:
                    raise serializers.ValidationError(
                        self.error_messages["invalid_image"]
                    )

            try:
                decoded_file = base64.b64decode(data, validate=True)
            except (TypeError, ValueError, binascii.Error):
                raise serializers.ValidationError(self.error_messages["invalid_image"])

            extension = imghdr.what(None, decoded_file) or "png"
            file_name = f"{uuid.uuid4()}.{extension}"
            data = ContentFile(decoded_file, name=file_name)
        return super().to_internal_value(data)
    

class UserSerializer(serializers.ModelSerializer):
    """Serializer do odczytu danych użytkownika."""
    full_name = serializers.CharField(read_only=True)

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
            "location",
            "role",
            "created_at",
            "updated_at",
            "deleted_at",
            "is_active",
            "is_staff",
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer do tworzenia nowego użytkownika."""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)
    last_name = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
            "image",
            "phone",
            "location",
            #"role",
        ]

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Hasła muszą być takie same."})

        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password", None)
        if not validated_data.get("last_name"):
            validated_data["last_name"] = ""
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
            "email",
            "password",
            "image",
            "phone",
            "role",
            "location",
            "is_active",
            "is_staff",
        ]

    def update(self, instance, validated_data):
        pwd = validated_data.pop("password", None)
        image = validated_data.pop("image", serializers.empty)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if image is not serializers.empty:
            if image is None:
                if instance.image:
                    instance.image.delete(save=False)
                instance.image = None
            else:
                instance.image = image
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
    address = AddressSerializer( )
    image = Base64ImageField(required=False, allow_null=True)

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
            "address",
        ]

    def validate(self, attrs):
        return attrs

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
    address = AddressSerializer(required=False)
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
            "address",
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
            "invitation_message",
            "invitation_confirmed",
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
            "invitation_message",
            "invitation_confirmed",
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
    

class OrganizationAddressSerializer(AddressSerializer):
    """Serializer adresu organizacji rozszerzony o dane organizacji."""

    organization_id = serializers.IntegerField(source="organization_id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_type = serializers.CharField(source="organization.type", read_only=True)

    class Meta(AddressSerializer.Meta):
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "organization_type",
            *AddressSerializer.Meta.fields,
        ]
