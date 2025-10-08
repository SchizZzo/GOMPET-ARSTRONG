from django.contrib.contenttypes.models import ContentType

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.like_counter import resolve_content_type
from common.models import Comment, Reaction, ReactionType

from .serializers import CommentSerializer, ContentTypeSerializer, ReactionSerializer

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

    Przykład akcji PUT /common/comments/{id}/
    z danymi:
    
    {"content_type":["To pole jest wymagane."],"object_id":["To pole jest wymagane."],"body":["To pole jest wymagane."]}
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


    Nasłuchiwanie zmian liczby reakcji (np. like'ów) w czasie rzeczywistym
    odbywa się przez WebSocket pod adresem:
    ws://localhost/ws/reactable/{articles.article}/{reactable_id}/

    z {articles.article} to nazwa modelu w formacie app_label.model,
    a {reactable_id} to ID obiektu, dla którego liczymy reakcje.

    Output przykładowej wiadomości WebSocket:
    {"reactable": {"id": 2, "type": "articles.article"}, "total_likes": 1}
    

    Dodawanie i usuwanie reakcji LIKE można też wykonać przez endpoint:
    POST http://localhost/common/reactions/  z danymi:
    {
        "reactable_type": "articles.article",  # lub ID ContentType
        "reactable_id": 20,                    # lub string z ID obiektu
        "reaction_type": "LIKE"                # typ reakcji (np. LIKE)
    }

    
    
   
    
    SPRAWDZANIE CZY UŻYTKOWNIK DODAŁ REAKCJĘ
    http://localhost/common/reactions/has-reaction/?reactable_type=articles.article&reactable_id=2
    to zwroci id reackji dla artykulu 2 dla zalogowanego uzytkownika
    
    {"reaction_id":8}

    w przeciwnym razie 
    
    {"reaction_id":0}


    Usuwanie reakcji LIKE można wykonać przez endpoint:
    DELETE http://localhost/common/reactions/{id}/   


    """
    queryset = Reaction.objects.all()
    serializer_class = ReactionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    http_method_names = ["get", "post", "put", "patch", "delete"]



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

    # @action(detail=False, methods=["delete"], url_path="like", url_name="remove-like")
    # def remove_like(self, request):
    #     """Usuwa reakcję LIKE bieżącego użytkownika dla wskazanego obiektu."""

    #     reactable_type = request.data.get("reactable_type") or request.query_params.get("reactable_type")
    #     reactable_id = request.data.get("reactable_id") or request.query_params.get("reactable_id")

    #     if reactable_type is None or reactable_id is None:
    #         return Response(
    #             {"detail": "Fields 'reactable_type' and 'reactable_id' are required."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     try:
    #         content_type = resolve_content_type(reactable_type)
    #     except ContentType.DoesNotExist:
    #         return Response(
    #             {"detail": "Invalid 'reactable_type'."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     try:
    #         reactable_id_int = int(reactable_id)
    #     except (TypeError, ValueError):
    #         return Response(
    #             {"detail": "Invalid 'reactable_id'."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     Reaction.objects.filter(
    #         user=request.user,
    #         reaction_type=ReactionType.LIKE,
    #         reactable_type=content_type,
    #         reactable_id=reactable_id_int,
    #     ).delete()

    #     return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["get"],
        url_path="has-reaction",
        url_name="has-reaction",
    )
    def has_reaction(self, request):
        """Zwraca ID reakcji bieżącego użytkownika dla obiektu, w przeciwnym razie 0."""
        reactable_type_param = request.query_params.get("reactable_type")
        reactable_id_param = request.query_params.get("reactable_id")
        reaction_type_param = request.query_params.get(
            "reaction_type", ReactionType.LIKE
        )

        missing_params = [
            name
            for name, value in (
                ("reactable_type", reactable_type_param),
                ("reactable_id", reactable_id_param),
            )
            if value is None
        ]

        if missing_params:
            missing_display = ", ".join(f"'{param}'" for param in missing_params)
            return Response(
                {"detail": f"Query parameter(s) {missing_display} are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reaction_type_value = reaction_type_param.upper()
        if reaction_type_value not in ReactionType.values:
            return Response(
                {"detail": "Invalid 'reaction_type'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reactable_content_type = resolve_content_type(reactable_type_param)
        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid 'reactable_type'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            reactable_id = int(reactable_id_param)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid 'reactable_id'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.is_authenticated:
            return Response({"reaction_id": 0})

        reaction_id = (
            Reaction.objects.filter(
                user=request.user,
                reaction_type=reaction_type_value,
                reactable_type=reactable_content_type,
                reactable_id=reactable_id,
            )
            .values_list("id", flat=True)
            .first()
        )

        return Response({"reaction_id": reaction_id or 0})


