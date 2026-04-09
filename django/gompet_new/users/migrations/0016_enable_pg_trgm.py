from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_species_label"),
    ]

    operations = [
        TrigramExtension(),
    ]