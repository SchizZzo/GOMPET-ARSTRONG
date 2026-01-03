from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0012_alter_user_last_name"),
        ("animals", "0025_alter_animal_birth_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="animal",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="animals",
                to="users.organization",
            ),
        ),
    ]
