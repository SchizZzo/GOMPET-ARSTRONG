from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from rest_framework import serializers, viewsets, permissions, filters, status
from rest_framework.response import Response
from .models import Article, ArticleCategory

from .serializers import ArticleSerializer, ArticlesLastSerializer, ArticleCategorySerializer

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

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

@extend_schema(
    tags=["articles"],
    description="API endpoint that allows Articles to be viewed or edited. Supports soft-delete on destroy."
)
class ArticleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Articles to be viewed or edited.
    Supports soft-delete on destroy.
    

    """
    queryset = Article.objects.filter(deleted_at__isnull=True)
    serializer_class = ArticleSerializer
    lookup_field = "slug"
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "author__username"]
    ordering_fields = ["-created_at", "-updated_at"]
    filterset_fields = {
        "categories": ["exact"],
        "categories__slug": ["exact"],
        
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


        

        return queryset.distinct().order_by('-created_at')
    
        

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        article.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

    
    
    

@extend_schema(
    tags=["articles_latest"],
    
)
class ArticlesLastViewSet(viewsets.ReadOnlyModelViewSet):
    """
    # Widok tylko do odczytu - Najnowsze artykuły
    Pobiera do określonej liczby nieusuniętych instancji **Article**, posortowanych malejąco według daty utworzenia.

    ## Parametry zapytania
    - `author` (str, opcjonalnie): filtr częściowy (case-insensitive) na nazwę użytkownika autora artykułu.
    - `categories` (int, opcjonalnie): filtruje po identyfikatorze kategorii.
    - `categories__slug` (str, opcjonalnie): filtruje po slug kategorii.
    - `limit` (int, opcjonalnie): maksymalna liczba zwracanych artykułów (domyślnie 10, jeśli brak lub nieprawidłowy).

    ## Funkcjonalności
    - Uwzględnia tylko artykuły, których `deleted_at` jest null.
    - Wspiera wyszukiwanie po tytule za pomocą standardowego parametru `search`.
    - Wspiera sortowanie po `created_at` za pomocą standardowego parametru `ordering`.
    - Wspiera filtrowanie po kategoriach.
    - Zastosowanie uprawnień `IsAuthenticatedOrReadOnly`.

    ## Przykład zapytania
    ```http
    GET /articles-latest/?author=johndoe&limit=5
    ```
    """
    queryset = Article.objects.filter(deleted_at__isnull=True).order_by('-created_at')
    serializer_class = ArticlesLastSerializer

    lookup_field = "slug"
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["-created_at"]
    filterset_fields = {
        "categories": ["exact"],
        "categories__slug": ["exact"],
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
class ArticleCategoryViewSet(viewsets.ModelViewSet):
    queryset = ArticleCategory.objects.filter(deleted_at__isnull=True)
    serializer_class = ArticleCategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
