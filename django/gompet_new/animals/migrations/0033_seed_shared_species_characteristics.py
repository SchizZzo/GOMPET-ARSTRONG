import re

from django.db import migrations


SHARED_DOG_CAT_CHARACTERISTICS = [
    "vaccinated",
    "neutered",
    "dewormed",
    "hasChip",
    "hasHealthBook",
]


def _normalize_label(name: str) -> str:
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", (name or "").strip())
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized.upper()


def seed_shared_species_characteristics(apps, schema_editor):
    Species = apps.get_model("users", "Species")
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    dog_species, _ = Species.objects.get_or_create(
        label="DOG",
        defaults={"name": "Dog"},
    )
    cat_species, _ = Species.objects.get_or_create(
        label="CAT",
        defaults={"name": "Cat"},
    )

    for species in (dog_species, cat_species):
        if not species.label:
            species.label = _normalize_label(species.name)
            species.save(update_fields=["label"])

    for characteristic_name in SHARED_DOG_CAT_CHARACTERISTICS:
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

        for species in (dog_species, cat_species):
            CharacteristicsForSpecies.objects.get_or_create(
                characteristics_id=characteristic.id,
                species_id=species.id,
            )


def unseed_shared_species_characteristics(apps, schema_editor):
    Species = apps.get_model("users", "Species")
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    cat_species = Species.objects.filter(label="CAT").first()
    if cat_species is None:
        return

    characteristic_ids = list(
        Characteristics.objects.filter(
            characteristic__in=SHARED_DOG_CAT_CHARACTERISTICS
        ).values_list("id", flat=True)
    )
    if not characteristic_ids:
        return

    # On reverse remove only CAT links, keep DOG defaults intact.
    CharacteristicsForSpecies.objects.filter(
        characteristics_id__in=characteristic_ids,
        species_id=cat_species.id,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_species_label"),
        ("animals", "0032_characteristicsforspecies_and_m2m"),
    ]

    operations = [
        migrations.RunPython(
            seed_shared_species_characteristics,
            unseed_shared_species_characteristics,
        ),
    ]
