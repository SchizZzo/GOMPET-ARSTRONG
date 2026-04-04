from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from users.models import OrganizationMember

from .models import Litter, LitterAnimal
from .serializers import LitterAnimalSerializer, LitterSerializer


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
            normalized_errors = errors
        else:
            normalized_errors = {"non_field_errors": errors}

        return {
            "status": status.HTTP_400_BAD_REQUEST,
            "code": self.VALIDATION_ERROR_CODE,
            "message": self.VALIDATION_ERROR_MESSAGE,
            "errors": normalized_errors,
        }



class _LitterAccessMixin:
    @staticmethod
    def _is_organization_member(user, organization_id: int) -> bool:
        if not user or not user.is_authenticated:
            return False
        return OrganizationMember.objects.filter(
            user=user,
            organization_id=organization_id,
            invitation_confirmed=True,
        ).exists()

    def _can_manage_litter(self, litter: Litter) -> bool:
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if litter.owner_id:
            return litter.owner_id == user.id
        if litter.organization_id:
            return (
                litter.organization.user_id == user.id
                or self._is_organization_member(user, litter.organization_id)
            )
        return False


LITTER_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="organization-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter litters by organization ID.",
    ),
    OpenApiParameter(
        name="user-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter litters by owner user ID.",
    ),
]


@extend_schema(
    tags=["litters", "organizations_miots", "litters_new_profile"],
    description="API endpoint that allows litters to be viewed or edited.",
)
@extend_schema_view(
    list=extend_schema(
        summary="Lista miotow z filtrami",
        description="Udostepnia filtry query dla listy miotow w Swagger UI.",
        parameters=LITTER_LIST_FILTER_PARAMETERS,
    )
)
class LitterViewSet(StandardizedErrorResponseMixin, _LitterAccessMixin, viewsets.ModelViewSet):
    queryset = Litter.objects.all()
    serializer_class = LitterSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        user = self.request.user
        owner = serializer.validated_data.get("owner")
        organization = serializer.validated_data.get("organization")

        if user.is_superuser:
            serializer.save()
            return

        if owner and owner.id != user.id:
            raise PermissionDenied("Cannot create litter for another owner.")

        if organization:
            if not (
                organization.user_id == user.id
                or self._is_organization_member(user, organization.id)
            ):
                raise PermissionDenied("Cannot create litter for this organization.")
            serializer.save(owner=None, organization=organization)
            return

        serializer.save(owner=user, organization=None)

    def perform_update(self, serializer):
        litter = serializer.instance
        if not self._can_manage_litter(litter):
            raise PermissionDenied("You do not have permission to modify this litter.")

        if not self.request.user.is_superuser:
            forbidden_fields = {"owner", "organization"} & set(self.request.data.keys())
            if forbidden_fields:
                raise PermissionDenied("Only superusers can reassign litter ownership.")

        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage_litter(instance):
            raise PermissionDenied("You do not have permission to delete this litter.")
        instance.delete()

    def get_queryset(self):
        qs = super().get_queryset()
        organization_id = self.request.query_params.get("organization-id")
        user_id = self.request.query_params.get("user-id")

        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        elif user_id:
            qs = qs.filter(owner_id=user_id)

        return qs


@extend_schema(
    tags=["litter-animals"],
    description="API endpoint that allows litter-animals to be viewed or edited.",
)
class LitterAnimalViewSet(StandardizedErrorResponseMixin, _LitterAccessMixin, viewsets.ModelViewSet):
    queryset = LitterAnimal.objects.all()
    serializer_class = LitterAnimalSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        litter = serializer.validated_data["litter"]
        if not self._can_manage_litter(litter):
            raise PermissionDenied("You do not have permission to modify this litter.")
        serializer.save()

    def perform_update(self, serializer):
        litter_animal = serializer.instance
        if not self._can_manage_litter(litter_animal.litter):
            raise PermissionDenied("You do not have permission to modify this litter.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_manage_litter(instance.litter):
            raise PermissionDenied("You do not have permission to delete this litter item.")
        instance.delete()
