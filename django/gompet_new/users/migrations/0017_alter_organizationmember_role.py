from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0016_enable_pg_trgm"),
    ]

    operations = [
        migrations.AlterField(
            model_name="organizationmember",
            name="role",
            field=models.CharField(
                choices=[
                    ("OWNER", "Właściciel / Kierownik"),
                    ("STAFF", "Pracownik"),
                    ("VOLUNTEER", "Wolontariusz"),
                    ("MODERATOR", "Moderator"),
                    ("PARTNER", "Partner"),
                    ("CONTENT", "Twórca treści"),
                    ("VIEWER", "Obserwator"),
                    ("ADMIN", "Administrator"),
                ],
                default="STAFF",
                max_length=20,
            ),
        ),
    ]
