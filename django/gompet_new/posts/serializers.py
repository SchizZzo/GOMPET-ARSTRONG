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

  
        
