from django.db import migrations, models
import django.db.models.deletion


def backfill_characteristics_species(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    Species = apps.get_model("users", "Species")

    dog_species = Species.objects.filter(label="DOG").first()
    if dog_species is None:
        dog_species = Species.objects.filter(name__iexact="Dog").first()
    if dog_species is None:
        dog_species = Species.objects.create(name="Dog", label="DOG")
    elif not dog_species.label:
        dog_species.label = "DOG"
        dog_species.save(update_fields=["label"])

    Characteristics.objects.filter(species__isnull=True).update(species=dog_species)


def reset_characteristics_species(apps, schema_editor):
    Characteristics = apps.get_model("animals", "Characteristics")
    Characteristics.objects.update(species=None)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_species_label"),
        ("animals", "0030_animalsbreedgroups_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="characteristics",
            name="species",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="characteristics",
                to="users.species",
            ),
        ),
        migrations.RunPython(backfill_characteristics_species, reset_characteristics_species),
    ]
