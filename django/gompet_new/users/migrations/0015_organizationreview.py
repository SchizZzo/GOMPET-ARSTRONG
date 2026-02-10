from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_alter_user_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationReview",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "score",
                    models.PositiveSmallIntegerField(
                        validators=[MinValueValidator(1), MaxValueValidator(5)]
                    ),
                ),
                ("comment", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="users.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="organization_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "organization_reviews",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="organizationreview",
            constraint=models.UniqueConstraint(
                fields=("organization", "user"),
                name="uniq_organization_review_user",
            ),
        ),
    ]
