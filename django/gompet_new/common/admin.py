

# Register your models here.
from django.contrib import admin
from .models import Comment, Reaction, Notification, Follow

admin.site.register(Comment)
admin.site.register(Reaction)
admin.site.register(Notification)
admin.site.register(Follow)
