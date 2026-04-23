from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    ArticleViewSet,
    ArticlesLastViewSet,
    ArticleCategoryViewSet,
    ArticleCategoryGroupViewSet,
)

router = DefaultRouter()
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'articles-latest', ArticlesLastViewSet, basename='articles-latest')
router.register(r'article-categories', ArticleCategoryViewSet, basename='article-category')
router.register(r'category-groups', ArticleCategoryGroupViewSet, basename='category-group')

urlpatterns = [
    path('', include(router.urls)),
]