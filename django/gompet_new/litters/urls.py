from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import LitterViewSet, LitterAnimalViewSet

# litters/urls.py


router = DefaultRouter()
router.register(r'litters', LitterViewSet, basename='litter')
router.register(r'litter-animals', LitterAnimalViewSet, basename='litter-animal')

urlpatterns = [
    path('', include(router.urls)),
]