from django.urls import path, include
from rest_framework import routers

# c:/Users/dawid/GOMPET_2/gompet_new/users/urls.py

from .api_views import (
    TokenCreateView,
    TokenRefreshView,
    UserViewSet,
    OrganizationViewSet,
    OrganizationMemberViewSet,
    OrganizationRecentlyAddedViewSet,
    OrganizationFilteringAddedViewSet,
    SpeciesViewSet,
)

router = routers.DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'organization-members', OrganizationMemberViewSet, basename='organizationmember')
router.register(r'organization-latest', OrganizationRecentlyAddedViewSet, basename='latestorganization')
router.register(r'organization-filtering', OrganizationFilteringAddedViewSet, basename='organizationfiltering')
router.register(r'species', SpeciesViewSet, basename='species')

urlpatterns = [
    path('auth/token/', TokenCreateView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include(router.urls)),
]