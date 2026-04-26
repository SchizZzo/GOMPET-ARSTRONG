from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from rest_framework import serializers, viewsets, permissions, filters, status
from rest_framework.response import Response
from .models import Article, ArticleCategory, ArticleCategoryGroup

from .serializers import ArticleSerializer, ArticlesLastSerializer, ArticleCategorySerializer

from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework.decorators import action
from common.exceptions import normalize_validation_errors


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



def _split_csv_param(value):
    if not value:
        return []

    if isinstance(value, (list, tuple)):
        items = []
        for entry in value:
            if not entry:
                continue
            items.extend([item.strip() for item in entry.split(",") if item.strip()])
        return items

    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_category_groups(groups):
    allowed_groups = {value for value, _ in ArticleCategoryGroup.choices}
    return [group for group in groups if group in allowed_groups]


ARTICLE_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="has-category",
        type=bool,
        location=OpenApiParameter.QUERY,
        description="Filter by presence of categories (true/false).",
    ),
    OpenApiParameter(
        name="category",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated category IDs (alias for categories).",
    ),
    OpenApiParameter(
        name="category-slug",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated category slugs (alias for categories__slug).",
    ),
    OpenApiParameter(
        name="category-group",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Single category group value or comma-separated list (alias for categories__group).",
    ),
    OpenApiParameter(
        name="category-groups",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Alias for category-group; supports comma-separated values.",
    ),
    OpenApiParameter(
        name="limit",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Maximum number of returned items.",
    ),
]

ARTICLES_LATEST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="author",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Author first name fragment (case-insensitive).",
    ),
    OpenApiParameter(
        name="limit",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Maximum number of returned items (default: 10).",
    ),
    OpenApiParameter(
        name="category-group",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Single category group value or comma-separated list (alias for categories__group).",
    ),
    OpenApiParameter(
        name="category-groups",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Alias for category-group; supports comma-separated values.",
    ),
]

ARTICLE_CATEGORY_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="group",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Single group value or comma-separated list of group values.",
    ),
    OpenApiParameter(
        name="groups",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Alias for group; supports comma-separated values.",
    ),
]

@extend_schema(
    tags=["articles"],
    description="API endpoint that allows Articles to be viewed or edited. Supports soft-delete on destroy."
)
@extend_schema_view(
    list=extend_schema(
        summary="Lista artykulow z filtrami",
        description="Udostepnia filtry query dla listy artykulow w Swagger UI.",
        parameters=ARTICLE_LIST_FILTER_PARAMETERS,
    )
)
class ArticleViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows Articles to be viewed or edited.
    Supports soft-delete on destroy.
    

    """
    queryset = Article.objects.filter(deleted_at__isnull=True)
    serializer_class = ArticleSerializer
    lookup_field = "slug"
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "author__username"]
    ordering_fields = ["-created_at", "-updated_at"]
    filterset_fields = {
        "categories": ["exact"],
        "categories__slug": ["exact"],
        "categories__group": ["exact"],
        
    }

    def get_queryset(self):
        queryset = Article.objects.filter(deleted_at__isnull=True)

        has_category_param = self.request.query_params.get("has-category")
        if has_category_param is not None:
            normalized = has_category_param.lower()
            truthy = {"1", "true", "yes", "on"}
            falsy = {"0", "false", "no", "off"}

            # Use annotation to reliably count many-to-many categories
            queryset = queryset.annotate(_cat_count=Count('categories'))
            if normalized in truthy:
                queryset = queryset.filter(_cat_count__gt=0)
            elif normalized in falsy:
                queryset = queryset.filter(_cat_count=0)

        category_param = self.request.query_params.getlist("category")
        category_ids = _split_csv_param(category_param)
        if category_ids:
            queryset = queryset.filter(categories__id__in=category_ids)

        category_slug_param = self.request.query_params.getlist("category-slug")
        category_slugs = _split_csv_param(category_slug_param)
        if category_slugs:
            queryset = queryset.filter(categories__slug__in=category_slugs)

        categories_param = self.request.query_params.getlist("categories")
        categories_ids = _split_csv_param(categories_param)
        if categories_ids:
            queryset = queryset.filter(categories__id__in=categories_ids)

        categories_slug_param = self.request.query_params.getlist("categories__slug")
        categories_slugs = _split_csv_param(categories_slug_param)
        if categories_slugs:
            queryset = queryset.filter(categories__slug__in=categories_slugs)

        category_group_values = _split_csv_param(self.request.query_params.getlist("category-group"))
        category_group_values.extend(
            _split_csv_param(self.request.query_params.getlist("category-groups"))
        )
        category_group_values.extend(
            _split_csv_param(self.request.query_params.getlist("categories__group"))
        )
        if category_group_values:
            normalized_category_groups = _normalize_category_groups(category_group_values)
            if normalized_category_groups:
                queryset = queryset.filter(categories__group__in=normalized_category_groups)
            else:
                queryset = queryset.none()




        return queryset.distinct().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limit_param = request.query_params.get('limit')
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except ValueError:
                limit = None
            if limit is not None and limit >= 0:
                queryset = queryset[:limit]
    
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        article.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

    
    
    

@extend_schema(
    tags=["articles_latest"],
    
)
@extend_schema_view(
    list=extend_schema(
        summary="Najnowsze artykuly z filtrami",
        description="Udostepnia filtry query dla listy najnowszych artykulow.",
        parameters=ARTICLES_LATEST_FILTER_PARAMETERS,
    )
)
class ArticlesLastViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    # Widok tylko do odczytu - Najnowsze artykuły
    Pobiera do określonej liczby nieusuniętych instancji **Article**, posortowanych malejąco według daty utworzenia.

    ## Parametry zapytania
    - `author` (str, opcjonalnie): filtr częściowy (case-insensitive) na nazwę użytkownika autora artykułu.
    - `categories` (int, opcjonalnie): filtruje po identyfikatorze kategorii.
    - `categories__slug` (str, opcjonalnie): filtruje po slug kategorii.
    - `category-group` (str, opcjonalnie): filtruje po grupie kategorii (pojedyncza wartość lub CSV).
    - `limit` (int, opcjonalnie): maksymalna liczba zwracanych artykułów (domyślnie 10, jeśli brak lub nieprawidłowy).

    ## Funkcjonalności
    - Uwzględnia tylko artykuły, których `deleted_at` jest null.
    - Wspiera wyszukiwanie po tytule za pomocą standardowego parametru `search`.
    - Wspiera sortowanie po `created_at` za pomocą standardowego parametru `ordering`.
    - Wspiera filtrowanie po kategoriach.
    - Zastosowanie uprawnień `DjangoModelPermissionsOrAnonReadOnly`.

    ## Przykład zapytania
    ```http
    GET /articles-latest/?author=johndoe&limit=5
    ```
    """
    queryset = Article.objects.filter(deleted_at__isnull=True).order_by('-created_at')
    serializer_class = ArticlesLastSerializer

    lookup_field = "slug"
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["-created_at"]
    filterset_fields = {
        "categories": ["exact"],
        "categories__slug": ["exact"],
        "categories__group": ["exact"],
    }
    


    def get_queryset(self):
        queryset = Article.objects.filter(deleted_at__isnull=True)
        author = self.request.query_params.get('author')
        if author:
            queryset = queryset.filter(author__first_name__icontains=author)

        categories_param = self.request.query_params.getlist("categories")
        categories_ids = _split_csv_param(categories_param)
        if categories_ids:
            queryset = queryset.filter(categories__id__in=categories_ids)

        categories_slug_param = self.request.query_params.getlist("categories__slug")
        categories_slugs = _split_csv_param(categories_slug_param)
        if categories_slugs:
            queryset = queryset.filter(categories__slug__in=categories_slugs)

        category_group_values = _split_csv_param(self.request.query_params.getlist("category-group"))
        category_group_values.extend(
            _split_csv_param(self.request.query_params.getlist("category-groups"))
        )
        category_group_values.extend(
            _split_csv_param(self.request.query_params.getlist("categories__group"))
        )
        if category_group_values:
            normalized_category_groups = _normalize_category_groups(category_group_values)
            if normalized_category_groups:
                queryset = queryset.filter(categories__group__in=normalized_category_groups)
            else:
                queryset = queryset.none()

        return queryset.distinct().order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limit_param = request.query_params.get('limit')
        try:
            limit = int(limit_param) if limit_param is not None else 10
        except ValueError:
            limit = 10

        queryset = queryset[:limit]

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema(
    tags=["article_categories"],
    description="API endpoint for managing article categories.",
)
@extend_schema_view(
    list=extend_schema(
        summary="Lista kategorii artykułów z filtrami",
        description="Udostepnia filtry query dla listy kategorii artykułów.",
        parameters=ARTICLE_CATEGORY_LIST_FILTER_PARAMETERS,
    )
)
class ArticleCategoryViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    queryset = ArticleCategory.objects.filter(deleted_at__isnull=True)
    serializer_class = ArticleCategorySerializer
    pagination_class = None
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug", "group"]
    ordering_fields = ["group", "name", "created_at"]

    def get_queryset(self):
        queryset = ArticleCategory.objects.filter(deleted_at__isnull=True)

        groups = _split_csv_param(self.request.query_params.getlist("group"))
        groups.extend(_split_csv_param(self.request.query_params.getlist("groups")))

        if groups:
            normalized_groups = _normalize_category_groups(groups)
            if normalized_groups:
                queryset = queryset.filter(group__in=normalized_groups)
            else:
                queryset = queryset.none()

        return queryset

    @extend_schema(
        summary="Lista grup kategorii artykułów",
        description="Zwraca wszystkie dostępne grupy kategorii wraz z liczbą aktywnych kategorii.",
        tags=["article_categories"],
    )
    @action(detail=False, methods=["get"], url_path="groups")
    def groups(self, request, *args, **kwargs):
        grouped_counts = {
            item["group"]: item["categories_count"]
            for item in self.get_queryset().values("group").annotate(categories_count=Count("id"))
        }

        data = [
            {
                "value": value,
                "label": label,
                "categories_count": grouped_counts.get(value, 0),
            }
            for value, label in ArticleCategoryGroup.choices
        ]
        return Response(data)


class ArticleCategoryGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    value = serializers.CharField()
    label = serializers.CharField()
    categories_count = serializers.IntegerField()


@extend_schema(
    tags=["article_categories"],
    description="API endpoint for listing article category groups.",
)
class ArticleCategoryGroupViewSet(viewsets.ViewSet):
    pagination_class = None
    permission_classes = [permissions.AllowAny]
    http_method_names = ["get", "head", "options"]

    @extend_schema(
        summary="Lista grup kategorii artykułów",
        description="Zwraca wszystkie dostępne grupy kategorii wraz z liczbą aktywnych kategorii.",
        responses=ArticleCategoryGroupSerializer(many=True),
    )
    def list(self, request):
        grouped_counts = {
            item["group"]: item["categories_count"]
            for item in ArticleCategory.objects.filter(deleted_at__isnull=True)
            .values("group")
            .annotate(categories_count=Count("id"))
        }

        data = [
            {
                "id": group_id,
                "value": value,
                "label": label,
                "categories_count": grouped_counts.get(value, 0),
            }
            for group_id, (value, label) in enumerate(ArticleCategoryGroup.choices, start=1)
        ]
        return Response(data)
