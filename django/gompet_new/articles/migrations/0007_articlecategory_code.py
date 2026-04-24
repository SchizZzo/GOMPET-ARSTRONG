from django.db import migrations, models
from django.utils.text import slugify


def populate_category_codes(apps, schema_editor):
    ArticleCategory = apps.get_model("articles", "ArticleCategory")

    used_codes = set(
        ArticleCategory.objects.exclude(code__isnull=True)
        .exclude(code__exact="")
        .values_list("code", flat=True)
    )

    for category in ArticleCategory.objects.all().order_by("id"):
        if category.code:
            used_codes.add(category.code)
            continue

        base_code = slugify(category.slug or category.name or f"category-{category.id}") or f"category-{category.id}"
        code = base_code
        suffix = 2
        while code in used_codes:
            code = f"{base_code}-{suffix}"
            suffix += 1

        category.code = code
        category.save(update_fields=["code"])
        used_codes.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0006_articlecategory_group_seed_defaults"),
    ]

    operations = [
        migrations.AddField(
            model_name="articlecategory",
            name="code",
            field=models.SlugField(blank=True, null=True, db_index=False),
        ),
        migrations.RunPython(populate_category_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="articlecategory",
            name="code",
            field=models.SlugField(blank=True, unique=True),
        ),
    ]
