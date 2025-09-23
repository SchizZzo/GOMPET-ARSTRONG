from urllib import request
from rest_framework import serializers
from .models import Post

class PostSerializer(serializers.ModelSerializer):
    """Serializer for the Post model."""

    animal_name = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()
    comments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    reactions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "animal_name",
            "organization_name",
            "organization",
            "animal",
            "author",
            "text",
            "created_at",
            "updated_at",
            "deleted_at",
            "image",
            "comments",
            "reactions",
        )

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
        animal_id = request.query_params.get("animal-id")
               
        if not animal_id:
            animal_id = self.context.get("animal_id") if isinstance(self.context, dict) else None

        
        if animal_id:
            qs = qs.filter(animal_id=animal_id)

        organization_id = request.query_params.get("organization-id")
        if organization_id:
            qs = qs.filter(organization_id=organization_id)

        return qs

  
        
