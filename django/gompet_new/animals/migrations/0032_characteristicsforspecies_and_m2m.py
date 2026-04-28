from django.db import migrations, models
import django.db.models.deletion


def migrate_species_fk_to_through(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    rows = []
    for characteristic in Characteristics.objects.exclude(species_id__isnull=True).iterator():
        rows.append(
            CharacteristicsForSpecies(
                characteristics_id=characteristic.id,
                species_id=characteristic.species_id,
            )
        )
    if rows:
        CharacteristicsForSpecies.objects.bulk_create(rows, ignore_conflicts=True)


def migrate_species_through_to_fk(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    CharacteristicsForSpecies = apps.get_model("animals", "CharacteristicsForSpecies")

    through_map = {}
    for row in CharacteristicsForSpecies.objects.all().order_by("id").iterator():
        through_map.setdefault(row.characteristics_id, row.species_id)

    for characteristic in Characteristics.objects.all().iterator():
        species_id = through_map.get(characteristic.id)
        if species_id:
            characteristic.species_id = species_id
            characteristic.save(update_fields=["species"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_species_label"),
        ("animals", "0031_characteristics_species"),
    ]

    operations = [
        migrations.CreateModel(
            name="CharacteristicsForSpecies",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "characteristics",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characteristics_for_species",
                        to="animals.characteristics",
                    ),
                ),
                (
                    "species",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="characteristics_for_species",
                        to="users.species",
                    ),
                ),
            ],
            options={
                "db_table": "characteristics_for_species",
                "unique_together": {("characteristics", "species")},
            },
        ),
        migrations.RunPython(
            migrate_species_fk_to_through,
            migrate_species_through_to_fk,
        ),
        migrations.RemoveField(
            model_name="characteristics",
            name="species",
        ),
        migrations.AddField(
            model_name="characteristics",
            name="species",
            field=models.ManyToManyField(
                blank=True,
                related_name="characteristicsForSpecies",
                through="animals.CharacteristicsForSpecies",
                to="users.species",
            ),
        ),
    ]
