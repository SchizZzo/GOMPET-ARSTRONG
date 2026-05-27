from django.db import migrations, models
from django.utils.text import slugify


def _build_unique_slug(organization_model, db_alias, name, organization_id=None):
    base_slug = slugify(name or "", allow_unicode=True) or f"organization-{organization_id or 'org'}"
    slug = base_slug
    existing = organization_model.objects.using(db_alias)
    suffix = 2

    while existing.filter(slug=slug).exclude(pk=organization_id).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


def populate_slugs(apps, schema_editor):
    Organization = apps.get_model("users", "Organization")
    db_alias = schema_editor.connection.alias

    for organization in Organization.objects.using(db_alias).all().only("id", "name", "slug"):
        if organization.slug:
            continue
        organization.slug = _build_unique_slug(
            Organization,
            db_alias,
            organization.name,
            organization.id,
        )
        organization.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0017_alter_organizationmember_role"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS organizations_slug_aaafa6fa_like;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddField(
            model_name="organization",
            name="slug",
            field=models.SlugField(blank=True, null=True, db_index=False),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS organizations_slug_aaafa6fa_like;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="organization",
            name="slug",
            field=models.SlugField(blank=True, unique=True),
        ),
    ]
