import json
import random
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.utils import timezone

from animals.models import Animal, AnimalStatus, AnimalsBreedGroups, Gender, LifePeriod, Size
from articles.models import Article
from common.models import Comment
from litters.models import Litter, LitterStatus
from posts.models import Post
from users.models import (
    Address,
    BreedingType,
    Organization,
    OrganizationBreedingType,
    OrganizationSpecies,
    OrganizationType,
    Species,
)


class Command(BaseCommand):
    help = "Populate database with realistic demo data."

    def handle(self, *args, **options):
        random.seed(20260522)
        User = get_user_model()

        city_map = [
            {"city": "Warszawa", "zip": "00-001", "lat": 52.2297, "lng": 21.0122, "street": "Pulawska"},
            {"city": "Krakow", "zip": "30-001", "lat": 50.0647, "lng": 19.9450, "street": "Wielicka"},
            {"city": "Wroclaw", "zip": "50-001", "lat": 51.1079, "lng": 17.0385, "street": "Legnicka"},
            {"city": "Gdansk", "zip": "80-001", "lat": 54.3520, "lng": 18.6466, "street": "Grunwaldzka"},
            {"city": "Poznan", "zip": "60-001", "lat": 52.4064, "lng": 16.9252, "street": "Bukowska"},
            {"city": "Lodz", "zip": "90-001", "lat": 51.7592, "lng": 19.4560, "street": "Pilsudskiego"},
            {"city": "Katowice", "zip": "40-001", "lat": 50.2649, "lng": 19.0238, "street": "Chorzowska"},
            {"city": "Lublin", "zip": "20-001", "lat": 51.2465, "lng": 22.5684, "street": "Krakowskie Przedmiescie"},
        ]

        def random_point(near=None):
            base = near or random.choice(city_map)
            lat = base["lat"] + random.uniform(-0.05, 0.05)
            lng = base["lng"] + random.uniform(-0.05, 0.05)
            return Point(lng, lat)

        users_seed = [
            ("koordynator@gompet.test", "Jan", "Nowicki"),
            ("ania.nowak@gompet.test", "Ania", "Nowak"),
            ("piotr.kowalski@gompet.test", "Piotr", "Kowalski"),
            ("marta.wisniewska@gompet.test", "Marta", "Wisniewska"),
            ("lukasz.wojcik@gompet.test", "Lukasz", "Wojcik"),
            ("ewa.kaminska@gompet.test", "Ewa", "Kaminska"),
            ("jakub.zielinski@gompet.test", "Jakub", "Zielinski"),
            ("agnieszka.mazur@gompet.test", "Agnieszka", "Mazur"),
            ("pawel.krawczyk@gompet.test", "Pawel", "Krawczyk"),
            ("karolina.piotrowska@gompet.test", "Karolina", "Piotrowska"),
            ("tomasz.grabowski@gompet.test", "Tomasz", "Grabowski"),
            ("monika.zajac@gompet.test", "Monika", "Zajac"),
        ]
        users = []
        for idx, (email, first_name, last_name) in enumerate(users_seed):
            city = city_map[idx % len(city_map)]
            users.append(
                User.objects.create_user(
                    email=email,
                    password="password123",
                    first_name=first_name,
                    last_name=last_name,
                    location=random_point(city),
                )
            )

        for species in OrganizationSpecies:
            Species.objects.get_or_create(name=species.label)
        for btype in OrganizationBreedingType:
            BreedingType.objects.get_or_create(name=btype.label)

        dog_species = Species.objects.get(name="Dog")
        breed_groups_file = Path(__file__).resolve().parent.parent.parent / "data" / "breed_groups.json"
        with breed_groups_file.open(encoding="utf-8") as handle:
            breed_groups_data = json.load(handle)
        for item in breed_groups_data:
            AnimalsBreedGroups.objects.update_or_create(
                group_name=item["group_name"],
                defaults={
                    "species": dog_species,
                    "min_weight": item["min_weight"],
                    "max_weight": item["max_weight"],
                    "min_size_male": item["min_size_male"],
                    "max_size_male": item["max_size_male"],
                    "min_size_famale": item["min_size_famale"],
                    "max_size_famale": item["max_size_famale"],
                },
            )
        breed_groups = list(AnimalsBreedGroups.objects.all())

        org_seed = [
            ("Schronisko Przyjazna Lapa", OrganizationType.SHELTER, "Schronisko miejskie, adopcje i interwencje."),
            ("Schronisko Zielony Azyl", OrganizationType.SHELTER, "Przyjecia zwierzat po interwencjach i leczenie."),
            ("Schronisko Miejski Ogon", OrganizationType.SHELTER, "Program domow tymczasowych i adopcji."),
            ("Fundacja Cztery Lapy", OrganizationType.FUND, "Wsparcie leczenia, kastracji i transportow."),
            ("Fundacja Dom Dla Zwierzat", OrganizationType.FUND, "Edukacja i wsparcie odpowiedzialnych adopcji."),
            ("Fundacja Nadzieja dla Futrzakow", OrganizationType.FUND, "Pomoc seniorom i zwierzetom przewlekle chorym."),
            ("Hodowla Bursztynowy Trop FCI", OrganizationType.BREEDER, "Domowa hodowla psow rasowych z badaniami."),
            ("Hodowla Lesny Nos FCI", OrganizationType.BREEDER, "Planowane mioty i socjalizacja szczeniat."),
            ("Hodowla Srebrna Luna FPL", OrganizationType.BREEDER, "Hodowla kotow z naciskiem na dobrostan."),
        ]
        organizations = []
        for idx, (name, org_type, description) in enumerate(org_seed):
            owner = users[idx % len(users)]
            city = city_map[idx % len(city_map)]
            org = Organization.objects.create(
                name=name,
                type=org_type,
                email=f"kontakt{idx+1}@gompet.test",
                user=owner,
                phone=f"+48 500 10{idx:02d} {idx+11:02d}",
                description={"pl": description},
            )
            address = Address.objects.create(
                organization=org,
                city=city["city"],
                street=city["street"],
                house_number=str(10 + idx),
                zip_code=city["zip"],
                lat=city["lat"],
                lng=city["lng"],
                location=random_point(city),
            )
            if org_type == OrganizationType.BREEDER:
                address.species.add(Species.objects.get(name="Dog"), Species.objects.get(name="Cat"))
            elif org_type == OrganizationType.FUND:
                address.species.add(Species.objects.get(name="Dog"), Species.objects.get(name="Cat"), Species.objects.get(name="Rabbit"))
            else:
                address.species.add(Species.objects.get(name="Dog"), Species.objects.get(name="Cat"))
            organizations.append(org)

        animal_images = Path(settings.MEDIA_ROOT) / "animals" / "images"
        org_images = Path(settings.MEDIA_ROOT) / "organizations" / "images"
        animal_image_pool = []
        org_image_pool = []
        if animal_images.exists():
            animal_image_pool = [
                p.name for p in animal_images.iterdir()
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
            ]
        if org_images.exists():
            org_image_pool = [
                p.name for p in org_images.iterdir()
                if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
            ]

        for org in organizations:
            if org_image_pool:
                org.image = f"organizations/images/{random.choice(org_image_pool)}"
                org.save(update_fields=["image", "updated_at"])

        animal_names = [
            "Luna", "Borys", "Mila", "Fado", "Kora", "Nero", "Miki", "Tofi", "Rosa", "Gaja",
            "Max", "Nela", "Ares", "Bambi", "Piksel", "Tosia", "Riko", "Bela", "Figa", "Rubi",
            "Aza", "Maja", "Bruno", "Leo", "Sonia", "Pola", "Dexter", "Moris", "Rufus", "Felek",
            "Zefir", "Mango", "Keks", "Poppy", "Frytka", "Otis", "Loki", "Nugat", "Runa", "Lola",
        ]
        breed_by_species = {
            "Dog": ["Mieszaniec", "Owczarek niemiecki mix", "Labrador mix", "Beagle mix", "Terier mix"],
            "Cat": ["Europejski krotkowlosy", "Dachowiec", "Mix Maine Coon", "Mix Brytyjski"],
            "Rabbit": ["Mini lop", "Karzelkowy", "Baranek"],
        }
        species_cycle = ["Dog", "Cat", "Rabbit", "Dog", "Cat"]
        animals = []
        for idx in range(40):
            org = organizations[idx % len(organizations)]
            owner = users[idx % len(users)]
            species = species_cycle[idx % len(species_cycle)]
            birth_date = timezone.now().date() - timedelta(days=random.randint(150, 4200))
            city_ref = city_map[idx % len(city_map)]
            animal = Animal.objects.create(
                name=f"{animal_names[idx]} {idx+1}",
                species=species,
                breed=random.choice(breed_by_species[species]),
                gender=Gender.MALE if idx % 2 == 0 else Gender.FEMALE,
                size=random.choice([Size.SMALL, Size.MEDIUM, Size.LARGE]),
                life_period=random.choice([LifePeriod.PUPPY, LifePeriod.ADULT, LifePeriod.SENIOR]),
                status=random.choice([AnimalStatus.AVAILABLE, AnimalStatus.RESERVED, AnimalStatus.ADOPTED]),
                birth_date=birth_date,
                owner=owner,
                organization=org,
                city=city_ref["city"],
                location=random_point(city_ref),
                animal_breed_groups=random.choice(breed_groups) if breed_groups else None,
                descriptions={
                    "pl": "Zwierze po podstawowej diagnostyce, zaszczepione i gotowe do procesu adopcyjnego."
                },
                image=f"animals/images/{random.choice(animal_image_pool)}" if animal_image_pool else None,
            )
            animals.append(animal)

        post_templates = [
            "Dzisiaj zakonczylismy kontrole weterynaryjna, podopieczny czuje sie stabilnie.",
            "Szukamy odpowiedzialnego domu tymczasowego na najblizsze dwa tygodnie.",
            "Zwierzak zaczyna ladnie pracowac na spacerach i dobrze reaguje na opiekuna.",
            "Potrzebujemy wsparcia w postaci karmy specjalistycznej i podkladow.",
            "Mamy wolne terminy na spotkania przedadopcyjne w tym tygodniu.",
            "Dziekujemy wolontariuszom za pomoc w transporcie i opiece weekendowej.",
            "Udana adopcja po serii spotkan, trzymamy kontakt z nowym domem.",
            "Przyjelismy nowe zwierzeta po interwencji, trwa diagnostyka i obserwacja.",
        ]
        posts = []
        for idx in range(65):
            author = users[idx % len(users)]
            if idx % 3 == 0:
                animal = random.choice(animals)
                post = Post.objects.create(
                    content=f"{random.choice(post_templates)} ({animal.name})",
                    author=author,
                    animal=animal,
                )
            else:
                org = random.choice(organizations)
                post = Post.objects.create(
                    content=f"{random.choice(post_templates)} ({org.name})",
                    author=author,
                    organization=org,
                )
            posts.append(post)

        for idx in range(12):
            slug = f"poradnik-adopcyjny-{idx+1}"
            Article.objects.create(
                slug=slug,
                title=f"Poradnik adopcyjny {idx+1}",
                content={"type": "text", "value": "Jak przygotowac dom i opieke po adopcji zwierzecia."},
                author=users[idx % len(users)],
            )

        for idx in range(14):
            Litter.objects.create(
                species=dog_species,
                breed=random.choice(breed_groups) if breed_groups else None,
                title=f"Miot {idx+1}",
                status=LitterStatus.ACTIVE,
                owner=users[idx % len(users)],
            )

        animal_ct = ContentType.objects.get_for_model(Animal)
        for idx, animal in enumerate(animals):
            Comment.objects.create(
                user=users[idx % len(users)],
                content_type=animal_ct,
                object_id=animal.id,
                body="Spokojny temperament, dobre rokowania adopcyjne i szybka adaptacja do nowych warunkow.",
            )

        post_ct = ContentType.objects.get_for_model(Post)
        for idx, post in enumerate(posts):
            for offset in range(1 if idx % 2 == 0 else 2):
                Comment.objects.create(
                    user=users[(idx + offset + 1) % len(users)],
                    content_type=post_ct,
                    object_id=post.id,
                    body="Dziekujemy za rzetelna aktualizacje, trzymamy kciuki za szybkie znalezienie domu.",
                )

        org_ct = ContentType.objects.get_for_model(Organization)
        for idx, org in enumerate(organizations):
            for offset in range(4):
                Comment.objects.create(
                    user=users[(idx + offset) % len(users)],
                    content_type=org_ct,
                    object_id=org.id,
                    body="Bardzo dobra komunikacja i przejrzysty proces adopcyjny.",
                    rating=random.randint(4, 5),
                )

        self.stdout.write(self.style.SUCCESS("Fresh realistic demo data inserted successfully."))
