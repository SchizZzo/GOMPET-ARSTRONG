from rest_framework import viewsets, permissions
from django.contrib.contenttypes.models import ContentType
from common.models import Comment, Reaction
from .serializers import CommentSerializer, ContentTypeSerializer, ReactionSerializer



from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework import serializers, viewsets, permissions

# common/api_serializers.py

@extend_schema(
    tags=["comments", "comments_organizations", "comments_orgazanizations_profile"],
    description="CRUD API dla komentarzy. GET list, POST create, PUT/PATCH update, DELETE delete."
)
class CommentViewSet(viewsets.ModelViewSet):
    """
    CRUD API dla komentarzy.
    GET list, POST create, PUT/PATCH update, DELETE delete.
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


    


@extend_schema(
    tags=["content_types"],
    description="Retrieve a list of all available ContentType entries."
)
class ContentTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read‐only endpoint for listing all ContentType entries.
    """
    queryset = ContentType.objects.all()
    serializer_class = ContentTypeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]




@extend_schema(
    tags=["reactions"],
    description="CRUD API dla reakcji. GET list, POST create, PUT/PATCH update, DELETE delete."
)
class ReactionViewSet(viewsets.ModelViewSet):
    """
    CRUD API dla reakcji.
    """
    queryset = Reaction.objects.all()
    serializer_class = ReactionSerializer
    permission_classes = [permissions.IsAuthenticated]


