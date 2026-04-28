from django.db import migrations


SPECIES_BREEDS = {
    "DOG": [
        "Labrador Retriever",
        "Golden Retriever",
        "German Shepherd",
        "French Bulldog",
        "Border Collie",
        "Beagle",
        "Yorkshire Terrier",
        "Shih Tzu",
        "Dachshund",
        "Poodle",
        "Cavalier King Charles Spaniel",
        "Siberian Husky",
        "Chihuahua",
        "Boxer",
        "Mixed Dog",
    ],
    "CAT": [
        "Domestic Shorthair",
        "Maine Coon",
        "British Shorthair",
        "Ragdoll",
        "Siamese",
        "Persian",
        "Bengal",
        "Sphynx",
        "Norwegian Forest Cat",
        "Russian Blue",
        "Abyssinian",
        "Scottish Fold",
        "Mixed Cat",
    ],
    "RABBIT": [
        "Mini Rex",
        "Holland Lop",
        "Netherland Dwarf",
        "Lionhead",
        "Mini Lop",
        "Flemish Giant",
        "English Angora",
        "Polish Rabbit",
        "Mixed Rabbit",
    ],
    "GUINEA_PIG": [
        "American Guinea Pig",
        "Abyssinian Guinea Pig",
        "Peruvian Guinea Pig",
        "Silkie Guinea Pig",
        "Teddy Guinea Pig",
        "Texel Guinea Pig",
        "Coronet Guinea Pig",
        "Mixed Guinea Pig",
    ],
    "HAMSTER": [
        "Syrian Hamster",
        "Campbells Dwarf Hamster",
        "Winter White Dwarf Hamster",
        "Roborovski Hamster",
        "Chinese Hamster",
        "Mixed Hamster",
    ],
    "RAT": [
        "Fancy Rat",
        "Dumbo Rat",
        "Rex Rat",
        "Hairless Rat",
        "Standard Rat",
        "Mixed Rat",
    ],
    "MOUSE": [
        "Fancy Mouse",
        "Hairless Mouse",
        "Long-haired Mouse",
        "Satin Mouse",
        "Mixed Mouse",
    ],
    "BIRD": [
        "Budgerigar",
        "Cockatiel",
        "Lovebird",
        "Canary",
        "African Grey Parrot",
        "Conure",
        "Finch",
        "Cockatoo",
        "Mixed Bird",
    ],
    "REPTILE": [
        "Leopard Gecko",
        "Crested Gecko",
        "Bearded Dragon",
        "Corn Snake",
        "Ball Python",
        "King Snake",
        "Red-eared Slider",
        "Russian Tortoise",
        "Mixed Reptile",
    ],
    "AMPHIBIAN": [
        "Axolotl",
        "Pacman Frog",
        "Tree Frog",
        "Dart Frog",
        "Tiger Salamander",
        "Fire Belly Newt",
        "Mixed Amphibian",
    ],
    "FISH": [
        "Betta",
        "Goldfish",
        "Guppy",
        "Molly",
        "Platy",
        "Neon Tetra",
        "Angelfish",
        "Discus",
        "Corydoras",
        "Mixed Fish",
    ],
    "OTHER": [
        "Small Mammal Other",
        "Exotic Bird Other",
        "Exotic Reptile Other",
        "Aquatic Other",
        "Mixed Other",
    ],
}


def _ensure_species(apps, label: str):
    Species = apps.get_model("users", "Species")
    species, _ = Species.objects.get_or_create(
        label=label,
        defaults={"name": label.title().replace("_", " ")},
    )
    return species


def _create_breed_group(apps, species, group_name: str):
    AnimalsBreedGroups = apps.get_model("animals", "AnimalsBreedGroups")
    existing = AnimalsBreedGroups.objects.filter(group_name=group_name).first()
    if existing:
        if existing.species_id == species.id:
            return
        unique_name = f"{group_name} ({species.label})"
        AnimalsBreedGroups.objects.get_or_create(
            group_name=unique_name,
            defaults={"species_id": species.id, "description": ""},
        )
        return

    AnimalsBreedGroups.objects.create(
        group_name=group_name,
        species_id=species.id,
        description="",
    )


def seed_breed_groups_for_all_species(apps, schema_editor):
    for species_label, breeds in SPECIES_BREEDS.items():
        species = _ensure_species(apps, species_label)
        for breed_name in breeds:
            _create_breed_group(apps, species, breed_name)


def unseed_breed_groups_for_all_species(apps, schema_editor):
    AnimalsBreedGroups = apps.get_model("animals", "AnimalsBreedGroups")
    candidate_names = set()
    for species_label, breeds in SPECIES_BREEDS.items():
        for breed_name in breeds:
            candidate_names.add(breed_name)
            candidate_names.add(f"{breed_name} ({species_label})")

    AnimalsBreedGroups.objects.filter(group_name__in=candidate_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_species_label"),
        ("animals", "0034_seed_characteristics_for_all_species"),
    ]

    operations = [
        migrations.RunPython(
            seed_breed_groups_for_all_species,
            unseed_breed_groups_for_all_species,
        ),
    ]

