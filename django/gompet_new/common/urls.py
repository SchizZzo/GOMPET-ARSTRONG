from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    CommentViewSet,
    ContentTypeViewSet,
    NotificationViewSet,
    ReactionViewSet,
    FollowViewSet,
)

router = DefaultRouter()

router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'reactions', ReactionViewSet, basename='reaction')
router.register(r'content-types', ContentTypeViewSet, basename='content-type')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'follows', FollowViewSet, basename='follow')

urlpatterns = [
    path('', include(router.urls)),
]