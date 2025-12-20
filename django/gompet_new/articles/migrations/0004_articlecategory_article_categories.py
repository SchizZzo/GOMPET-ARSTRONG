from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("articles", "0003_alter_article_author"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArticleCategory",
            fields=[
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=150, unique=True)),
                ("slug", models.SlugField(unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "db_table": "article_categories",
                "ordering": ("name",),
            },
        ),
        migrations.AddField(
            model_name="article",
            name="categories",
            field=models.ManyToManyField(blank=True, related_name="articles", to="articles.articlecategory"),
        ),
    ]
