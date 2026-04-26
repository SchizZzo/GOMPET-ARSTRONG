from django.contrib.contenttypes.models import ContentType

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from common.like_counter import resolve_content_type
from common.models import Comment, Follow, Notification, Reaction, ReactionType
from common.exceptions import normalize_validation_errors

from .serializers import (
    CommentSerializer,
    ContentTypeSerializer,
    NotificationSerializer,
    ReactionSerializer,
    FollowSerializer,
)

class StandardizedErrorResponseMixin:
    """Helper for explicit 400 responses built inside action methods."""

    VALIDATION_ERROR_CODE = "ERR_GENERIC_VALIDATION"
    VALIDATION_ERROR_MESSAGE = "Validation error."

    def _build_validation_error_payload(self, errors):
        if errors is None:
            normalized_errors = {}
        elif isinstance(errors, dict):
            normalized_errors = normalize_validation_errors(errors)
        else:
            normalized_errors = {
                "non_field_errors": normalize_validation_errors(errors)
            }

        return {
            "status": status.HTTP_400_BAD_REQUEST,
            "code": self.VALIDATION_ERROR_CODE,
            "message": self.VALIDATION_ERROR_MESSAGE,
            "errors": normalized_errors,
        }

    def validation_error_response(self, errors):
        return Response(
            self._build_validation_error_payload(errors),
            status=status.HTTP_400_BAD_REQUEST,
        )


COMMENT_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="object_id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter comments by target object ID.",
    ),
    OpenApiParameter(
        name="content_type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Content type ID or app_label.model.",
    ),
    OpenApiParameter(
        name="limit",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Maximum number of returned comments.",
    ),
]

REACTION_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="reactable_id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter reactions by target object ID.",
    ),
    OpenApiParameter(
        name="reactable_type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Content type ID or app_label.model.",
    ),
]

FOLLOW_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="target_id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter follows by target object ID.",
    ),
    OpenApiParameter(
        name="target_type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Content type ID or app_label.model.",
    ),
]

# common/api_serializers.py

@extend_schema(
    tags=["comments", "comments_organizations", "comments_orgazanizations_profile"],
    description="CRUD API dla komentarzy. GET list, POST create, PUT/PATCH update, DELETE delete."
)
@extend_schema_view(
    list=extend_schema(
        summary="Lista komentarzy z filtrami",
        description="Udostepnia filtry query dla listy komentarzy.",
        parameters=COMMENT_LIST_FILTER_PARAMETERS,
    )
)
class CommentViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
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
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]

    def _can_manage_comment(self, comment: Comment) -> bool:
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or comment.user_id == user.id

    def get_queryset(self):
        """
        Optionally restricts the returned comments to a given object,
        by filtering against `content_type` and `object_id` query parameters in the URL.
        """
        queryset = Comment.objects.all()
        object_id = self.request.query_params.get('object_id')
        content_type_id = self.request.query_params.get('content_type')
        limit = self.request.query_params.get('limit')

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

        if limit is not None:
            try:
                limit_value = int(limit)
            except (TypeError, ValueError):
                limit_value = None

            if limit_value is not None and limit_value > 0:
                queryset = queryset[:limit_value]
            
        return queryset

    def perform_update(self, serializer):
        comment = serializer.instance
        if not self._can_manage_comment(comment):
            raise PermissionDenied("You do not have permission to modify this comment.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage_comment(instance):
            raise PermissionDenied("You do not have permission to delete this comment.")
        instance.delete()


    


@extend_schema(
    tags=["content_types"],
    description="Retrieve a list of all available ContentType entries."
)
class ContentTypeViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
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
@extend_schema_view(
    list=extend_schema(
        summary="Lista reakcji z filtrami",
        description="Udostepnia filtry query dla listy reakcji.",
        parameters=REACTION_LIST_FILTER_PARAMETERS,
    )
)
class ReactionViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
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
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def _can_manage_reaction(self, reaction: Reaction) -> bool:
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or reaction.user_id == user.id



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

    def perform_update(self, serializer):
        reaction = serializer.instance
        if not self._can_manage_reaction(reaction):
            raise PermissionDenied("You do not have permission to modify this reaction.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage_reaction(instance):
            raise PermissionDenied("You do not have permission to delete this reaction.")
        instance.delete()

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
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_MISSING_QUERY_PARAMS",
                        "message": f"Query parameter(s) {missing_display} are required.",
                    }
                }
            )

        reaction_type_value = reaction_type_param.upper()
        if reaction_type_value not in ReactionType.values:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_QUERY_REACTION_TYPE_INVALID",
                        "message": "Invalid 'reaction_type'.",
                    }
                }
            )

        try:
            reactable_content_type = resolve_content_type(reactable_type_param)
        except ContentType.DoesNotExist:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_QUERY_REACTABLE_TYPE_INVALID",
                        "message": "Invalid 'reactable_type'.",
                    }
                }
            )

        try:
            reactable_id = int(reactable_id_param)
        except (TypeError, ValueError):
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_QUERY_REACTABLE_ID_INVALID",
                        "message": "Invalid 'reactable_id'.",
                    }
                }
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


@extend_schema(
    tags=["notifications"],
    description="Lista powiadomień zalogowanego użytkownika oraz oznaczanie ich jako przeczytane.",
)
class NotificationViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    queryset = Notification.objects.select_related("actor").all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return self.queryset.filter(recipient=self.request.user).order_by("-created_at")

    def partial_update(self, request, *args, **kwargs):
        disallowed_fields = set(request.data.keys()) - {"is_read"}
        if disallowed_fields:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_ONLY_IS_READ_UPDATABLE",
                        "message": "Only 'is_read' can be updated.",
                    }
                }
            )

        return super().partial_update(request, *args, **kwargs)



@extend_schema(
    tags=["follows"],
    description="CRUD API dla obserwowanych obiektów (polimorficznie).",
)
@extend_schema_view(
    list=extend_schema(
        summary="Lista obserwowanych obiektow z filtrami",
        description="Udostepnia filtry query dla listy follow.",
        parameters=FOLLOW_LIST_FILTER_PARAMETERS,
    )
)
class FollowViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Follow.objects.filter(user=self.request.user)

        target_id = self.request.query_params.get("target_id")
        target_type = self.request.query_params.get("target_type")

        if target_id is not None:
            queryset = queryset.filter(target_id=target_id)

        if target_type is not None:
            if "." in target_type:
                try:
                    app_label, model = target_type.split(".")
                    content_type_obj = ContentType.objects.get_by_natural_key(app_label, model)
                    queryset = queryset.filter(target_type=content_type_obj)
                except ContentType.DoesNotExist:
                    return queryset.none()
            else:
                queryset = queryset.filter(target_type_id=target_type)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["get"], url_path="is-following", url_name="is-following")
    def is_following(self, request):
        target_type_param = request.query_params.get("target_type")
        target_id_param = request.query_params.get("target_id")

        if target_type_param is None or target_id_param is None:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_MISSING_TARGET_PARAMS",
                        "message": "Query parameters 'target_type' and 'target_id' are required.",
                    }
                }
            )

        try:
            target_content_type = resolve_content_type(target_type_param)
        except ContentType.DoesNotExist:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_TARGET_TYPE_INVALID",
                        "message": "Invalid 'target_type'.",
                    }
                }
            )

        try:
            target_id = int(target_id_param)
        except (TypeError, ValueError):
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_TARGET_ID_INVALID",
                        "message": "Invalid 'target_id'.",
                    }
                }
            )

        follow_id = (
            Follow.objects.filter(
                user=request.user,
                target_type=target_content_type,
                target_id=target_id,
            )
            .values_list("id", flat=True)
            .first()
        )

        return Response({"follow_id": follow_id or 0})

    @action(
        detail=False,
        methods=["get"],
        url_path="followers-count",
        url_name="followers-count",
        permission_classes=[permissions.IsAuthenticatedOrReadOnly],
    )
    def followers_count(self, request):
        target_type_param = request.query_params.get("target_type")
        target_id_param = request.query_params.get("target_id")

        if target_type_param is None or target_id_param is None:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_MISSING_TARGET_PARAMS",
                        "message": "Query parameters 'target_type' and 'target_id' are required.",
                    }
                }
            )

        try:
            target_content_type = resolve_content_type(target_type_param)
        except ContentType.DoesNotExist:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_TARGET_TYPE_INVALID",
                        "message": "Invalid 'target_type'.",
                    }
                }
            )

        if (
            target_content_type.app_label,
            target_content_type.model,
        ) not in {("users", "organization"), ("animals", "animal")}:
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_TARGET_SCOPE_INVALID",
                        "message": "'target_type' must be users.organization or animals.animal.",
                    }
                }
            )

        try:
            target_id = int(target_id_param)
        except (TypeError, ValueError):
            return self.validation_error_response(
                {
                    "detail": {
                        "code": "ERR_TARGET_ID_INVALID",
                        "message": "Invalid 'target_id'.",
                    }
                }
            )

        followers_count = Follow.objects.filter(
            target_type=target_content_type,
            target_id=target_id,
        ).count()

        return Response({"followers_count": followers_count})
