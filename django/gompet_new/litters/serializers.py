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
            "birth_date",
            "status",
            "species",
            "breed",
            "owner",
            "organization",
            "created_at",
            "updated_at",
            "deleted_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["species"] = instance.species.name if instance.species else None
        data["breed"] = instance.breed.group_name if instance.breed else None
        return data
