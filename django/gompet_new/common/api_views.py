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

    {
    "content_type": 26,  # ID ContentType (np. Post, Article)
     # można też użyć "content_type": "posts.post",

    "object_id": 20,
        # ID obiektu powiązanego z komentarzem (np. Post, Article)
        # można też użyć "object_id": "20",
        
    "body": "TEKST KKOMENTARZA"
}
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        """
        Optionally restricts the returned comments to a given object,
        by filtering against `content_type` and `object_id` query parameters in the URL.
        """
        queryset = Comment.objects.all()
        object_id = self.request.query_params.get('object_id')
        content_type_id = self.request.query_params.get('content_type')

        if object_id is not None:
            queryset = queryset.filter(object_id=object_id)
        
        if content_type_id is not None:
            # Sprawdź, czy content_type jest stringiem w formacie 'app_label.model'
            if '.' in content_type_id:
                try:
                    app_label, model = content_type_id.split('.')
                    content_type_obj = ContentType.objects.get_by_natural_key(app_label, model)
                    queryset = queryset.filter(content_type=content_type_obj)
                except ContentType.DoesNotExist:
                    # Opcjonalnie: obsłuż błąd, jeśli podany content_type nie istnieje
                    # Na przykład, zwracając pusty queryset
                    return queryset.none()
            else:
                # Zakładamy, że to ID
                queryset = queryset.filter(content_type_id=content_type_id)
            
        return queryset


    


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

    def get_queryset(self):
        """
        Optionally restricts the returned reactions to a given object,
        by filtering against `reactable_type` and `reactable_id` query parameters in the URL.
        """
        queryset = Reaction.objects.all()
        reactable_id = self.request.query_params.get('reactable_id')
        reactable_type = self.request.query_params.get('reactable_type')

        if reactable_id is not None:
            queryset = queryset.filter(reactable_id=reactable_id)
        
        if reactable_type is not None:
            # Sprawdź, czy reactable_type jest stringiem w formacie 'app_label.model'
            if '.' in reactable_type:
                try:
                    app_label, model = reactable_type.split('.')
                    content_type_obj = ContentType.objects.get_by_natural_key(app_label, model)
                    queryset = queryset.filter(reactable_type=content_type_obj)
                except ContentType.DoesNotExist:
                    # Opcjonalnie: obsłuż błąd, jeśli podany reactable_type nie istnieje
                    # Na przykład, zwracając pusty queryset
                    return queryset.none()
            else:
                # Zakładamy, że to ID
                queryset = queryset.filter(reactable_type_id=reactable_type)
            
        return queryset


