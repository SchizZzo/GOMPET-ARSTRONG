from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Article, ArticleCategory


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "get_categories", "slug", "author", "created_at", "deleted_at")
    list_filter = ("deleted_at", "created_at", "author")
    search_fields = ("title", "content", "author__username", "author__email")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("-created_at",)
    raw_id_fields = ("author",)

    def get_categories(self, obj):
        return ", ".join([category.name for category in obj.categories.all()])
    get_categories.short_description = "Categories"
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    fieldsets = (
        (None, {
            "fields": ("title", "categories", "slug", "author", "content", "image")
        }),
        ("Date Information", {
            "fields": ("created_at", "updated_at", "deleted_at"),
            "classes": ("collapse",)
        }),
    )

@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)