from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import (
    AnimalViewSet,
    AnimalCharacteristicViewSet,
    AnimalGalleryViewSet,
    AnimalParentViewSet,
    AnimalFamilyTreeViewSet,
    CharacteristicsViewSet,
    AnimalsBreedGroupsViewSet,
)

router = DefaultRouter()
router.register(r'animals', AnimalViewSet, basename='animal')
router.register(r'animal-breed', AnimalsBreedGroupsViewSet, basename='animalbreed')
router.register(r'characteristics', AnimalCharacteristicViewSet, basename='animalcharacteristic')
router.register(r'characteristics-values', CharacteristicsViewSet, basename='characteristicsvalues')
router.register(r'galleries', AnimalGalleryViewSet, basename='animalgallery')
router.register(r'parents', AnimalParentViewSet, basename='animalparent')
router.register(r'family-tree', AnimalFamilyTreeViewSet, basename='animalfamilytree')


urlpatterns = [
    path('', include(router.urls)),
]