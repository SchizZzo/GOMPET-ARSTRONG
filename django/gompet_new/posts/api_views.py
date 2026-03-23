import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from animals.models import Animal
from common.models import Follow
from users.models import Organization, OrganizationMember
from .models import Post
from .serializers import PostSerializer

# posts/api_views.py

from drf_spectacular.utils import extend_schema

logger = logging.getLogger(__name__)


class StandardizedErrorResponseMixin:
    """Return consistent error payloads for selected HTTP statuses."""

    VALIDATION_ERROR_CODE = "validation_error"
    VALIDATION_ERROR_MESSAGE = "Validation error."

    ERROR_PAYLOADS = {
        status.HTTP_401_UNAUTHORIZED: (
            "not_authenticated",
            "Authentication credentials were not provided.",
        ),
        status.HTTP_403_FORBIDDEN: (
            "permission_denied",
            "You do not have permission to perform this action.",
        ),
        status.HTTP_404_NOT_FOUND: (
            "not_found",
            "Resource not found.",
        ),
        status.HTTP_500_INTERNAL_SERVER_ERROR: (
            "server_error",
            "An internal server error occurred.",
        ),
    }

    def _build_error_payload(self, status_code):
        code, message = self.ERROR_PAYLOADS[status_code]
        return {
            "status": status_code,
            "code": code,
            "message": message,
            "errors": {},
        }

    @staticmethod
    def _is_standard_error_payload(data):
        return (
            isinstance(data, dict)
            and {"status", "code", "message", "errors"}.issubset(data.keys())
        )

    def _build_validation_error_payload(self, errors):
        if errors is None:
            normalized_errors = {}
        elif isinstance(errors, dict):
            normalized_errors = errors
        else:
            normalized_errors = {"non_field_errors": errors}

        return {
            "status": status.HTTP_400_BAD_REQUEST,
            "code": self.VALIDATION_ERROR_CODE,
            "message": self.VALIDATION_ERROR_MESSAGE,
            "errors": normalized_errors,
        }

    def handle_exception(self, exc):
        try:
            response = super().handle_exception(exc)
        except Exception:
            logger.exception("Unhandled exception in %s", self.__class__.__name__)
            if settings.DEBUG:
                raise
            return Response(
                self._build_error_payload(status.HTTP_500_INTERNAL_SERVER_ERROR),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if response is None:
            return response

        if self._is_standard_error_payload(response.data):
            return response

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            response.data = self._build_validation_error_payload(response.data)
        elif response.status_code in self.ERROR_PAYLOADS:
            response.data = self._build_error_payload(response.status_code)

        return response



class FeedPagePagination(PageNumberPagination):
    page_size = 10


@extend_schema(
    tags=["posts", "posts_organizations", "posts_animals"],
    description="API endpoint to list and create posts."
)
class PostViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    """
    PostViewSet
    ===========

    Endpoint REST do pobierania i zarzĂ„â€¦dzania postami (obiekty **Post**).

    DostĂ„â„˘pne metody HTTP
    --------------------
    - **GET /posts/** Ă˘â‚¬â€ś lista postÄ‚Ĺ‚w z moÄąÄ˝liwoÄąâ€şciĂ„â€¦ filtrowania  
    - **POST /posts/** Ă˘â‚¬â€ś utworzenie nowego postu  
    - **GET /posts/{id}/** Ă˘â‚¬â€ś szczegÄ‚Ĺ‚Äąâ€šy pojedynczego postu  
    - **PUT /posts/{id}/**, **PATCH /posts/{id}/** Ă˘â‚¬â€ś aktualizacja  
    - **DELETE /posts/{id}/** Ă˘â‚¬â€ś usuniĂ„â„˘cie

    Parametry zapytania (lista)
    ---------------------------
    - **animal-id** (int, opcjonalny)  
      ID zwierzĂ„â„˘cia; zwraca posty powiĂ„â€¦zane z danym zwierzĂ„â„˘ciem
      (`Post.animal_id`).

    - **organization-id** (int, opcjonalny)  
      ID organizacji; zwraca posty dotyczĂ„â€¦ce wskazanej organizacji
      (`Post.organization_id`).

    Zasady filtrowania
    ------------------
    - JeÄąÄ˝eli podasz **oba** parametry, rezultaty muszĂ„â€¦ speÄąâ€šniaĂ„â€ˇ *oba*
      warunki (operator AND).  
    - Brak parametrÄ‚Ĺ‚w Ă˘â€ â€™ zwracane sĂ„â€¦ wszystkie posty.

    PrzykÄąâ€šady
    ---------
    ```http
    # Posty dla zwierzĂ„â„˘cia o ID 17
    GET /posts/?animal-id=17

    # Posty organizacji 5
    GET /posts/?organization-id=5

    # Posty zwierzĂ„â„˘cia 17 w organizacji 5
    GET /posts/?animal-id=17&organization-id=5
    ```


    Aktualizacja postu 

    PUT posts/posts/{id}/
    -----------------
    z danymi:
    {
    "content": "NOWY POST"
    }



    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [
        DjangoModelPermissionsOrAnonReadOnly,
    ] # KaÄąÄ˝dy moÄąÄ˝e czytaĂ„â€ˇ, ale tworzyĂ„â€ˇ/edytowaĂ„â€ˇ tylko zalogowani

    def _ensure_user_can_modify_animal(self, serializer):
        user = self.request.user
        animal = serializer.validated_data.get("animal")
        if animal is None and getattr(serializer, "instance", None) is not None:
            animal = serializer.instance.animal

        organization = serializer.validated_data.get("organization")
        if organization is None and getattr(serializer, "instance", None) is not None:
            organization = serializer.instance.organization

        if animal and not user.is_superuser:
            is_owner = animal.owner_id == user.id
            is_member_of_animal_org = False
            if animal.organization_id:
                is_member_of_animal_org = OrganizationMember.objects.filter(
                    user=user,
                    organization_id=animal.organization_id,
                    invitation_confirmed=True,
                ).exists()
            if not is_owner and not is_member_of_animal_org:
                raise PermissionDenied(
                    "Tylko wĹ‚aĹ›ciciel zwierzÄ™cia lub czĹ‚onek jego organizacji moĹĽe modyfikowaÄ‡ post."
                )

        if organization and not user.is_superuser:
            is_org_owner = organization.user_id == user.id
            is_org_member = OrganizationMember.objects.filter(
                user=user,
                organization=organization,
                invitation_confirmed=True,
            ).exists()
            if not is_org_owner and not is_org_member:
                raise PermissionDenied(
                    "Tylko wĹ‚aĹ›ciciel organizacji lub jej czĹ‚onek moĹĽe modyfikowaÄ‡ post."
                )

    def perform_create(self, serializer):
        self._ensure_user_can_modify_animal(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_user_can_modify_animal(serializer)
        serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        animal_id = self.request.query_params.get("animal-id")
        organization_id = self.request.query_params.get("organization-id")
        if animal_id:
            qs = qs.filter(animal_id=animal_id)
        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        return qs

    @action(
        detail=False,
        methods=["get"],
        url_path="feed",
        permission_classes=[IsAuthenticatedOrReadOnly],
        pagination_class=FeedPagePagination,
    )
    def feed(self, request):
        total_feed_limit = 1000
        followed_ratio_limit = 700  
        random_ratio_limit = 300

        animal_ct = ContentType.objects.get_for_model(Animal)
        organization_ct = ContentType.objects.get_for_model(Organization)

        followed_animal_ids = []
        followed_organization_ids = []

        if request.user.is_authenticated:
            followed_animal_ids = list(
                Follow.objects.filter(
                    user=request.user,
                    target_type=animal_ct,
                    notification_preferences__posts=True,
                ).values_list("target_id", flat=True)
            )

            followed_organization_ids = list(
                Follow.objects.filter(
                    user=request.user,
                    target_type=organization_ct,
                    notification_preferences__posts=True,
                ).values_list("target_id", flat=True)
            )

        has_followed_entities = bool(followed_animal_ids or followed_organization_ids)

        if not has_followed_entities:
            queryset = list(Post.objects.order_by("-created_at")[:total_feed_limit])
        else:
            followed_posts = list(
                Post.objects.filter(
                    Q(animal_id__in=followed_animal_ids)
                    | Q(organization_id__in=followed_organization_ids)
                )
                .order_by("-created_at")[:followed_ratio_limit]
            )
            random_posts = list(
                Post.objects.exclude(
                    Q(animal_id__in=followed_animal_ids)
                    | Q(organization_id__in=followed_organization_ids)
                )
                .order_by("?")[:random_ratio_limit]
            )
            queryset = [*followed_posts, *random_posts]
            queryset.sort(key=lambda post: post.created_at, reverse=True)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="feed-test",
        permission_classes=[IsAuthenticatedOrReadOnly],
        pagination_class=FeedPagePagination,
    )
    def feed_test(self, request):
        animal_ct = ContentType.objects.get_for_model(Animal)
        organization_ct = ContentType.objects.get_for_model(Organization)

        followed_animal_ids = []
        followed_organization_ids = []

        if request.user.is_authenticated:
            followed_animal_ids = list(
                Follow.objects.filter(
                    user=request.user,
                    target_type=animal_ct,
                    notification_preferences__posts=True,
                ).values_list("target_id", flat=True)
            )

            followed_organization_ids = list(
                Follow.objects.filter(
                    user=request.user,
                    target_type=organization_ct,
                    notification_preferences__posts=True,
                ).values_list("target_id", flat=True)
            )

        queryset = Post.objects.filter(
            Q(animal_id__in=followed_animal_ids)
            | Q(organization_id__in=followed_organization_ids)
        ).order_by("-created_at")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.has_perm("posts.delete_post") and instance.author_id != user.id:
            raise PermissionDenied(
                "Only the post author or an administrator can delete this post."
            )
        super().perform_destroy(instance)


