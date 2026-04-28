import re

from django.db import migrations


SPECIES_CHARACTERISTICS_MAP = {
    "DOG": [
        "vaccinated",
        "neutered",
        "dewormed",
        "hasChip",
        "hasHealthBook",
        "childrenFriendly",
        "acceptsDogs",
        "acceptsCats",
        "learnsFast",
        "canLiveInACity",
        "needsMentalStimulation",
        "watchdog",
    ],
    "CAT": [
        "vaccinated",
        "neutered",
        "dewormed",
        "hasChip",
        "hasHealthBook",
        "childrenFriendly",
        "acceptsCats",
        "canLiveInACity",
        "clean",
        "calmAtHome",
    ],
    "RABBIT": [
        "vaccinated",
        "dewormed",
        "hasHealthBook",
        "childrenFriendly",
        "clean",
        "calmAtHome",
        "specialDiet",
        "gentle",
    ],
    "GUINEA_PIG": [
        "dewormed",
        "hasHealthBook",
        "childrenFriendly",
        "clean",
        "calmAtHome",
        "specialDiet",
        "gentle",
    ],
    "HAMSTER": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "calmAtHome",
        "specialDiet",
    ],
    "RAT": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "childrenFriendly",
        "learnsFast",
        "gentle",
    ],
    "MOUSE": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "calmAtHome",
    ],
    "BIRD": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "calmAtHome",
        "learnsFast",
    ],
    "REPTILE": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "calmAtHome",
        "specialDiet",
    ],
    "AMPHIBIAN": [
        "dewormed",
        "hasHealthBook",
        "clean",
        "specialDiet",
    ],
    "FISH": [
        "hasHealthBook",
        "clean",
        "calmAtHome",
        "specialDiet",
    ],
    "OTHER": [
        "hasHealthBook",
        "clean",
    ],
}


def _normalize_label(name: str) -> str:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", (name or "").strip())
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized.upper()


def seed_characteristics_for_all_species(apps, schema_editor):
    Species = apps.get_model("users", "Species")
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    for species_label, characteristics_names in SPECIES_CHARACTERISTICS_MAP.items():
        species, _ = Species.objects.get_or_create(
            label=species_label,
            defaults={"name": species_label.title().replace("_", " ")},
        )
        if not species.label:
            species.label = _normalize_label(species.name)
            species.save(update_fields=["label"])

        for characteristic_name in characteristics_names:
            characteristic, _ = Characteristics.objects.get_or_create(
                characteristic=characteristic_name,
                defaults={
                    "label": _normalize_label(characteristic_name),
                    "description": "",
                },
            )
            if not characteristic.label:
                characteristic.label = _normalize_label(characteristic.characteristic)
                characteristic.save(update_fields=["label"])

            CharacteristicsForSpecies.objects.get_or_create(
                characteristics_id=characteristic.id,
                species_id=species.id,
            )


def unseed_characteristics_for_all_species(apps, schema_editor):
    Species = apps.get_model("users", "Species")
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    characteristic_ids = list(
        Characteristics.objects.filter(
            characteristic__in={
                name
                for names in SPECIES_CHARACTERISTICS_MAP.values()
                for name in names
            }
        ).values_list("id", flat=True)
    )
    if not characteristic_ids:
        return

    species_ids = list(
        Species.objects.filter(label__in=SPECIES_CHARACTERISTICS_MAP.keys()).values_list("id", flat=True)
    )
    if not species_ids:
        return

    CharacteristicsForSpecies.objects.filter(
        characteristics_id__in=characteristic_ids,
        species_id__in=species_ids,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_species_label"),
        ("animals", "0033_seed_shared_species_characteristics"),
    ]

    operations = [
        migrations.RunPython(
            seed_characteristics_for_all_species,
            unseed_characteristics_for_all_species,
        ),
    ]

