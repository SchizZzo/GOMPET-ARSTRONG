from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display  = ("id", "title", "author", "created_at", "deleted_at")
    list_filter   = ("deleted_at", "created_at")
    search_fields = ("title", "content", "author__email")
    prepopulated_fields = {"slug": ("title",)}
    ordering      = ("-created_at",)