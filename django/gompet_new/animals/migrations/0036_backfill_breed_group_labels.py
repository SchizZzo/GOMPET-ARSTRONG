import re
import unicodedata

from django.db import migrations


BREED_LABEL_TOKEN_TRANSLATIONS = {
    "miniaturowy": "MINIATURE",
    "owczarek": "SHEPHERD",
    "amerykanski": "AMERICAN",
    "bialy": "WHITE",
    "szwajcarski": "SWISS",
    "slowacki": "SLOVAK",
    "chorwacki": "CROATIAN",
    "francuski": "FRENCH",
    "holenderski": "DUTCH",
    "katalonski": "CATALAN",
    "niemiecki": "GERMAN",
    "pikardyjski": "PICARDY",
    "pirenejski": "PYRENEAN",
    "poludnioworosyjski": "SOUTH_RUSSIAN",
    "portugalski": "PORTUGUESE",
    "staroangielski": "OLD_ENGLISH",
    "szetlandzki": "SHETLAND",
    "szkocki": "SCOTTISH",
    "majorki": "MAJORCA",
    "polski": "POLISH",
    "nizinny": "LOWLAND",
    "podhalanski": "TATRA",
    "dlugowlosy": "LONG_HAIRED",
    "krotkowlosy": "SHORT_HAIRED",
    "szorstkowlosy": "ROUGH_HAIRED",
    "juzak": "YUZHAK",
    "kolorowy": "COLORED",
    "ciobanesc": "SHEPHERD",
    "romanesc": "ROMANIAN",
    "pes": "DOG",
}
BREED_LABEL_STOPWORDS = {"a", "z", "typ"}


def normalize_label(group_name: str) -> str:
    if not isinstance(group_name, str):
        return ""

    ascii_group_name = (
        unicodedata.normalize("NFKD", group_name).encode("ascii", "ignore").decode("ascii")
    )
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_group_name).strip("_")
    if not normalized:
        return ""

    tokens = [token.lower() for token in normalized.split("_") if token]
    translated_tokens = [
        BREED_LABEL_TOKEN_TRANSLATIONS.get(token, token.upper())
        for token in tokens
        if token not in BREED_LABEL_STOPWORDS
    ]
    return "_".join(translated_tokens)


def backfill_labels(apps, schema_editor):
    AnimalsBreedGroups = apps.get_model("animals", "AnimalsBreedGroups")
    for group in AnimalsBreedGroups.objects.all().iterator():
        new_label = normalize_label(group.group_name)
        if group.label != new_label:
            group.label = new_label
            group.save(update_fields=["label"])


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0035_seed_breed_groups_for_all_species"),
    ]

    operations = [
        migrations.RunPython(backfill_labels, migrations.RunPython.noop),
    ]

