from __future__ import annotations

from typing import Iterable

from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import MemberRole, Organization, OrganizationMember
from .role_permissions import ROLE_PERMISSIONS


class OrganizationRolePermissions(BasePermission):
    """
    Weryfikuje uprawnienia na podstawie roli użytkownika w organizacji.

    - Dla globalnych przypadków (np. uprawnienia nadawane globalnie) stosuje standardowe
      sprawdzenie `user.has_perms`.
    - Dla obiektów powiązanych z organizacją korzysta z roli w `OrganizationMember`
      oraz mapowania `ROLE_PERMISSIONS`.
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        required_perms = self._get_required_perms(request.method, view)
        if required_perms and user.has_perms(required_perms):
            return True

        organization = self._get_organization(request, view=view)
        if not organization:
            return True

        return self._has_role_permissions(user, organization, required_perms)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        required_perms = self._get_required_perms(request.method, view)
        if required_perms and user.has_perms(required_perms):
            return True

        organization = self._get_organization(request, view=view, obj=obj)
        if not organization:
            return False

        return self._has_role_permissions(user, organization, required_perms)

    def _get_required_perms(self, method: str, view) -> list[str]:
        model = self._get_model(view)
        if not model:
            return []
        perms = self.perms_map.get(method, [])
        return [
            perm % {"app_label": model._meta.app_label, "model_name": model._meta.model_name}
            for perm in perms
        ]

    def _get_model(self, view):
        queryset = getattr(view, "queryset", None)
        if queryset is not None:
            return queryset.model
        if hasattr(view, "get_queryset"):
            return view.get_queryset().model
        return None

    def _get_organization(self, request, view=None, obj=None) -> Organization | None:
        if obj is not None:
            if isinstance(obj, Organization):
                return obj
            if hasattr(obj, "organization"):
                return obj.organization

        organization_id = (
            request.data.get("organization")
            if hasattr(request, "data")
            else None
        )
        if organization_id is None and hasattr(request, "data"):
            organization_id = request.data.get("organization_id")
        organization_id = organization_id or request.query_params.get("organization-id")
        organization_id = organization_id or request.query_params.get("organization")
        if organization_id:
            return Organization.objects.filter(pk=organization_id).first()

        return None

    def _has_role_permissions(
        self,
        user,
        organization: Organization,
        required_perms: Iterable[str],
    ) -> bool:
        membership = OrganizationMember.objects.filter(
            user=user,
            organization=organization,
        ).first()
        if not membership:
            return False

        try:
            role = MemberRole(membership.role)
        except ValueError:
            return False

        role_permissions = ROLE_PERMISSIONS.get(role, [])
        if not required_perms:
            return True
        return all(permission in role_permissions for permission in required_perms)
