from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Litter, LitterAnimal

User = get_user_model()


class LitterAnimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = LitterAnimal
        fields = (
            "id",
            "litter",
            "animal",
            "updated_at",
            "deleted_at",
        )


class LitterSerializer(serializers.ModelSerializer):
    
  
    class Meta:
        model = Litter
        fields = (
            "id",
            "title",
            "description",
            "status",
            "owner",
            "organization",
            "created_at",
            "updated_at",
            "deleted_at",
        )

    