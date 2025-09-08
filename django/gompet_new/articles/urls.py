from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import ArticleViewSet, ArticlesLastViewSet

router = DefaultRouter()
router.register(r'articles', ArticleViewSet, basename='article')
router.register(r'articles-latest', ArticlesLastViewSet, basename='articles-latest')

urlpatterns = [
    path('', include(router.urls)),
]