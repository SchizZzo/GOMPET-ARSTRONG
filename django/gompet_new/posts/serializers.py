from urllib import request
from rest_framework import serializers
from .models import Post

from users.serializers import UserSerializer, OrganizationSerializer


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
    
class PostSerializer(serializers.ModelSerializer):
    """Serializer for the Post model."""

    animal_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    comments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    image = Base64ImageField(required=False, allow_null=True)

    author = UserSerializer(read_only=True)

    organization_info  =  OrganizationSerializer(source="organization", read_only=True)
    class Meta:
        model = Post
        fields = (
            "id",
            "animal_name",
            "organization_name",
            
            "organization",
            "organization_info",
            "animal",
            "author",
            "content",
            "created_at",
            "updated_at",
            "deleted_at",
            "image",
            "comments",
            "reactions",
        )
        read_only_fields = ("author",)


    def get_animal_name(self, obj):
        # Pobiera nazwę zwierzęcia z powiązanego modelu Animal
        return obj.animal.name if obj.animal else None
    
    def get_organization_name(self, obj):
        # Pobiera nazwę organizacji z powiązanego modelu Organization
        return obj.organization.name if obj.organization else None
    
    
    
    def create(self, validated_data):
        """
        Automatycznie ustawia autora posta na aktualnie zalogowanego użytkownika.
        """
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
    
    def queryset(self):
        """
        Zwraca queryset przefiltrowany po animal_id (z request.query_params lub z context).
        Jeśli nie podano animal_id zwraca wszystkie posty.
        """
        qs = Post.objects.all()
        animal_id = self.context['request'].query_params.get("animal-id")
               
        if not animal_id:
            animal_id = self.context.get("animal_id") if isinstance(self.context, dict) else None

        
        if animal_id:
            qs = qs.filter(animal_id=animal_id)

        organization_id = self.context['request'].query_params.get("organization-id")
        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        return qs
