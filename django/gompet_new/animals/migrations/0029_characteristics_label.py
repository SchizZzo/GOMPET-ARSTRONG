import re

from django.db import migrations, models


def normalize_label(name: str) -> str:
    if not isinstance(name, str):
        return ""
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", name.strip())
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized.upper()


def backfill_characteristics_label(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    for characteristic in Characteristics.objects.all():
        characteristic.label = normalize_label(characteristic.characteristic)
        characteristic.save(update_fields=["label"])


class Migration(migrations.Migration):

    dependencies = [
        ("animals", "0028_seed_default_dog_characteristics"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteristics",
            name="label",
            field=models.CharField(blank=True, db_index=True, default="", max_length=120),
        ),
        migrations.RunPython(backfill_characteristics_label, migrations.RunPython.noop),
    ]

