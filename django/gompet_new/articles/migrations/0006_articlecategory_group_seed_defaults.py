from django.db import migrations, models
from django.utils.text import slugify


CATEGORY_GROUP_BASICS = "basics"
CATEGORY_GROUP_BY_SPECIES = "by_species"
CATEGORY_GROUP_DAILY_CARE = "daily_care"
CATEGORY_GROUP_TRAINING = "training"
CATEGORY_GROUP_HEALTH = "health"
CATEGORY_GROUP_SHOPPING = "shopping"
CATEGORY_GROUP_LIFESTYLE = "lifestyle"


SEEDED_ARTICLE_CATEGORIES = [
    (CATEGORY_GROUP_BASICS, "Żywienie zwierząt"),
    (CATEGORY_GROUP_BASICS, "Zdrowie i weterynaria"),
    (CATEGORY_GROUP_BASICS, "Pielęgnacja (higiena, sierść, pazury)"),
    (CATEGORY_GROUP_BASICS, "Akcesoria i wyposażenie"),
    (CATEGORY_GROUP_BASICS, "Zachowanie zwierząt"),
    (CATEGORY_GROUP_BY_SPECIES, "Psy"),
    (CATEGORY_GROUP_BY_SPECIES, "Koty"),
    (CATEGORY_GROUP_BY_SPECIES, "Gryzonie (chomiki, świnki morskie)"),
    (CATEGORY_GROUP_BY_SPECIES, "Ptaki"),
    (CATEGORY_GROUP_BY_SPECIES, "Ryby akwariowe"),
    (CATEGORY_GROUP_BY_SPECIES, "Gady i płazy"),
    (CATEGORY_GROUP_DAILY_CARE, "Karmienie"),
    (CATEGORY_GROUP_DAILY_CARE, "Spacery i aktywność"),
    (CATEGORY_GROUP_DAILY_CARE, "Higiena i czyszczenie"),
    (CATEGORY_GROUP_DAILY_CARE, "Sen i odpoczynek"),
    (CATEGORY_GROUP_DAILY_CARE, "Bezpieczeństwo w domu"),
    (CATEGORY_GROUP_TRAINING, "Tresura psów"),
    (CATEGORY_GROUP_TRAINING, "Nauka czystości"),
    (CATEGORY_GROUP_TRAINING, "Socjalizacja"),
    (CATEGORY_GROUP_TRAINING, "Zabawy i stymulacja"),
    (CATEGORY_GROUP_HEALTH, "Szczepienia"),
    (CATEGORY_GROUP_HEALTH, "Choroby i objawy"),
    (CATEGORY_GROUP_HEALTH, "Pierwsza pomoc"),
    (CATEGORY_GROUP_HEALTH, "Wizyty u weterynarza"),
    (CATEGORY_GROUP_SHOPPING, "Karma"),
    (CATEGORY_GROUP_SHOPPING, "Zabawki"),
    (CATEGORY_GROUP_SHOPPING, "Legowiska"),
    (CATEGORY_GROUP_SHOPPING, "Transportery"),
    (CATEGORY_GROUP_SHOPPING, "Kosmetyki dla zwierząt"),
    (CATEGORY_GROUP_LIFESTYLE, "Podróże ze zwierzętami"),
    (CATEGORY_GROUP_LIFESTYLE, "Adopcja zwierząt"),
    (CATEGORY_GROUP_LIFESTYLE, "Opieka nad starszymi zwierzętami"),
    (CATEGORY_GROUP_LIFESTYLE, "Opieka nad szczeniakami/kociętami"),
]


def _build_unique_slug(category_model, db_alias, name, category_id=None):
    base_slug = slugify(name) or "article-category"
    slug = base_slug
    suffix = 2

    existing = category_model.objects.using(db_alias)
    while existing.filter(slug=slug).exclude(pk=category_id).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


def seed_article_categories(apps, schema_editor):
    ArticleCategory = apps.get_model("articles", "ArticleCategory")
    db_alias = schema_editor.connection.alias

    for group, name in SEEDED_ARTICLE_CATEGORIES:
        category, created = ArticleCategory.objects.using(db_alias).get_or_create(
            name=name,
            defaults={
                "group": group,
                "slug": _build_unique_slug(ArticleCategory, db_alias, name),
                "description": "",
            },
        )

        if created:
            continue

        changed_fields = []

        if category.group != group:
            category.group = group
            changed_fields.append("group")

        if not category.slug:
            category.slug = _build_unique_slug(ArticleCategory, db_alias, name, category.id)
            changed_fields.append("slug")

        if category.deleted_at is not None:
            category.deleted_at = None
            changed_fields.append("deleted_at")

        if changed_fields:
            category.save(update_fields=changed_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0005_alter_article_content_alter_article_slug_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="articlecategory",
            name="group",
            field=models.CharField(
                choices=[
                    ("basics", "🐾 Podstawowe kategorie"),
                    ("by_species", "🐶 Podział według gatunków"),
                    ("daily_care", "🏠 Opieka codzienna"),
                    ("training", "🧠 Szkolenie i rozwój"),
                    ("health", "🏥 Zdrowie"),
                    ("shopping", "🛒 Zakupy i produkty"),
                    ("lifestyle", "🧳 Styl życia"),
                ],
                db_index=True,
                default="basics",
                max_length=32,
            ),
        ),
        migrations.RunPython(seed_article_categories, migrations.RunPython.noop),
    ]
