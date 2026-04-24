from django.db import migrations


ENGLISH_CATEGORY_CODES_BY_ID = {
    1: "ANIMAL_HUSBANDRY",
    2: "HABITATS",
    3: "ANIMAL_NUTRITION",
    4: "VETERINARY_HEALTH",
    5: "GROOMING_HYGIENE_CLAW_CARE",
    6: "ACCESSORIES_EQUIPMENT",
    7: "ANIMAL_BEHAVIOR",
    8: "DOGS",
    9: "CATS",
    10: "RODENTS",
    11: "BIRDS",
    12: "AQUARIUM_FISH",
    13: "REPTILES_AMPHIBIANS",
    14: "FEEDING",
    15: "WALKS_ACTIVITY",
    16: "HYGIENE_CLEANING",
    17: "SLEEP_REST",
    18: "HOME_SAFETY",
    19: "DOG_TRAINING",
    20: "HOUSE_TRAINING",
    21: "SOCIALIZATION",
    22: "PLAY_ENRICHMENT",
    23: "VACCINATIONS",
    24: "DISEASES_SYMPTOMS",
    25: "FIRST_AID",
    26: "VETERINARY_VISITS",
    27: "PET_FOOD",
    28: "TOYS",
    29: "PET_BEDS",
    30: "CARRIERS",
    31: "PET_COSMETICS",
    32: "PET_TRAVEL",
    33: "PET_ADOPTION",
    34: "SENIOR_PET_CARE",
    35: "PUPPY_KITTEN_CARE",
}


def set_english_codes(apps, schema_editor):
    ArticleCategory = apps.get_model("articles", "ArticleCategory")

    for category_id, code in ENGLISH_CATEGORY_CODES_BY_ID.items():
        ArticleCategory.objects.filter(id=category_id).update(code=code)


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0007_articlecategory_code"),
    ]

    operations = [
        migrations.RunPython(set_english_codes, migrations.RunPython.noop),
    ]
