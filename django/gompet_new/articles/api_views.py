from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response
from .models import Article

from .serializers import ArticleSerializer

from drf_spectacular.utils import extend_schema

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
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "content", "author__username"]
    ordering_fields = ["created_at", "updated_at"]
    MAX_LIMIT = 50

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        queryset = Article.objects.filter(deleted_at__isnull=True)
        author = self.request.query_params.get('author')
        if author:
            queryset = queryset.filter(author__first_name__icontains=author)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limit_param = request.query_params.get('limit')
        limit = None
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                limit = None
            else:
                limit = max(1, min(limit, self.MAX_LIMIT))
        if limit is not None:
            queryset = queryset[:limit]

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        article.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
    

