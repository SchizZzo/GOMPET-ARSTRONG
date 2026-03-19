from django.db import migrations


DOG_CHARACTERISTIC_NAMES = [
    "vaccinated",
    "neutered",
    "dewormed",
    "hasChip",
    "acceptsCats",
    "acceptsDogs",
    "clean",
    "hypoallergenic",
    "noSeparationAnxiety",
    "suitableForApartment",
    "vigorous",
    "childrenFriendly",
    "learnsFast",
    "specialDiet",
    "calmAtHome",
    "canLiveInACity",
    "needsMentalStimulation",
    "gentle",
    "watchdog",
    "hasHealthBook",
]


def seed_default_dog_characteristics(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    for characteristic_name in DOG_CHARACTERISTIC_NAMES:
        Characteristics.objects.get_or_create(
            characteristic=characteristic_name,
            defaults={"description": ""},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0027_alter_animal_organization"),
    ]

    operations = [
        migrations.RunPython(seed_default_dog_characteristics, migrations.RunPython.noop),
    ]

