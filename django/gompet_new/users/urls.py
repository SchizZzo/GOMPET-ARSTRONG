from django.urls import path, include
from rest_framework import routers

# c:/Users/dawid/GOMPET_2/gompet_new/users/urls.py

from .api_views import (
    TokenCreateView,
    TokenRefreshView,
    UserViewSet,
    DeleteMeView,
    OrganizationViewSet,
    OrganizationMemberViewSet,
    OrganizationRecentlyAddedViewSet,
    OrganizationFilteringAddedViewSet,
    SpeciesViewSet,
)


class UserRouter(routers.DefaultRouter):
    def get_routes(self, viewset):
        routes = super().get_routes(viewset)

        if hasattr(viewset, "destroy_current"):
            for route in routes:
                # Only inspect default routes whose mapping is a standard dict.
                # Extra actions use a MethodMapper which exposes a .get method
                # that expects a callable, not a key, so guard against it here.
                if isinstance(route.mapping, dict) and route.mapping.get("get") == "list":
                    route.mapping["delete"] = "destroy_current"

        return routes

router = UserRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'organization-members', OrganizationMemberViewSet, basename='organizationmember')
router.register(r'organization-latest', OrganizationRecentlyAddedViewSet, basename='latestorganization')
router.register(r'organization-filtering', OrganizationFilteringAddedViewSet, basename='organizationfiltering')
router.register(r'species', SpeciesViewSet, basename='species')

urlpatterns = [
    path('auth/token/', TokenCreateView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/me/delete/', DeleteMeView.as_view(), name='user-delete-me'),
    path('', include(router.urls)),
]