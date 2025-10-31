from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from animals.models import (
    Animal,
    Gender,
    Size,
    AnimalsBreedGroups,
)
from posts.models import Post
from users.models import (
    Species,
    BreedingType,
    OrganizationSpecies,
    OrganizationBreedingType,
    Organization,
    OrganizationType,
)
from articles.models import Article
from litters.models import Litter, LitterStatus
from common.models import Comment
import random

import json
from pathlib import Path


class Command(BaseCommand):
    help = "Populate the database with sample data."

    def handle(self, *args, **options):
        User = get_user_model()

        # create a default user if none exists
        if not User.objects.exists():
            user = User.objects.create_user(
                email="user@example.com",
                password="password",
                first_name="John",
                last_name="Doe",
            )
        else:
            user = User.objects.first()

        # create species
        for species in OrganizationSpecies:
            Species.objects.get_or_create(name=species.label)

        # ensure a generic "Dog" species exists for sample data
        dog_species, _ = Species.objects.get_or_create(name="Dog")

        # create breeding types
        for btype in OrganizationBreedingType:
            BreedingType.objects.get_or_create(name=btype.label)

        data_file = Path(__file__).resolve().parent.parent.parent / "data" / "breed_groups.json"
        with data_file.open() as f:
            breed_groups_data = json.load(f)

        for data in breed_groups_data:
            AnimalsBreedGroups.objects.update_or_create(
                group_name=data["group_name"],
                defaults={
                    "species": dog_species,
                    "min_weight": data["min_weight"],
                    "max_weight": data["max_weight"],
                    "min_size_male": data["min_size_male"],
                    "max_size_male": data["max_size_male"],
                    "min_size_famale": data["min_size_famale"],
                    "max_size_famale": data["max_size_famale"],
                },
            )

        breed_groups = list(AnimalsBreedGroups.objects.all())

        # create animals
        animals = []
        for i in range(20):
            lat = 52 + random.uniform(-0.5, 0.5)
            lng = 21 + random.uniform(-0.5, 0.5)
            animal = Animal.objects.create(
                name=f"Animal {i+1}",
                species="Dog",
                breed="Mixed",
                gender=Gender.MALE if i % 2 == 0 else Gender.FEMALE,
                size=Size.MEDIUM,
                owner=user,
                city=f"City {i+1}",
                location=Point(lng, lat),
            )
            animals.append(animal)

        # create organizations
        organizations = []
        for i in range(5):
            org = Organization.objects.create(
                type=OrganizationType.SHELTER,
                name=f"Organization {i+1}",
                email=f"org{i+1}@example.com",
                user=user,
            )
            organizations.append(org)

        # create posts
        posts = []
        for i in range(20):
            if random.choice([True, False]):
                animal = random.choice(animals)
                post = Post.objects.create(
                    content=f"Sample post {i+1}",
                    author=user,
                    animal=animal,
                )
                
            else:
                org = random.choice(organizations)
                post = Post.objects.create(
                    content=f"Sample post {i+1}",
                    author=user,
                    organization=org,
                )
            posts.append(post)

        # create articles
        for i in range(20):
            Article.objects.create(
                slug=f"article-{i+1}",
                title=f"Article {i+1}",
                content="Sample content",
                author=user,
            )

        # create litters
        for i in range(20):
            Litter.objects.create(
                species=dog_species,
                breed=random.choice(breed_groups),
                title=f"Litter {i+1}",
                status=LitterStatus.ACTIVE,
                owner=user,
            )

        # create comments for the animals
        animal_ct = ContentType.objects.get_for_model(Animal)
        for idx, animal in enumerate(animals):
            Comment.objects.create(
                user=user,
                content_type=animal_ct,
                object_id=animal.id,
                body=f"Comment {idx+1} on {animal.name}",
            )

        self.stdout.write(self.style.SUCCESS("Database populated with sample data."))
