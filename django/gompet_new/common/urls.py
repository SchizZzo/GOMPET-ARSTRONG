from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (

    CommentViewSet,
    ReactionViewSet,
    ContentTypeViewSet
)

router = DefaultRouter()

router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'reactions', ReactionViewSet, basename='reaction')
router.register(r'content-types', ContentTypeViewSet, basename='content-type')

urlpatterns = [
    path('', include(router.urls)),
]