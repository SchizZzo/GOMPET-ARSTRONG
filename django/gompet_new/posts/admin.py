from django.contrib import admin

# Register your models here.
# posts/admin.py
from django.contrib import admin
from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ("id", "author", "animal", "organization", "created_at", "deleted_at")
    list_filter   = ("deleted_at", )
    search_fields = ("text", "author__email")
    ordering      = ("-created_at",)
