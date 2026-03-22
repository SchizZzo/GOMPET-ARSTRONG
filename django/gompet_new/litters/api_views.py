from rest_framework import status, viewsets
from rest_framework.response import Response
from .models import Litter, LitterAnimal
from .serializers import LitterSerializer, LitterAnimalSerializer


from drf_spectacular.utils import extend_schema


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

    def handle_exception(self, exc):
        try:
            response = super().handle_exception(exc)
        except Exception:
            return Response(
                self._build_error_payload(status.HTTP_500_INTERNAL_SERVER_ERROR),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if response is None:
            return response

        if self._is_standard_error_payload(response.data):
            return response

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            response.data = self._build_validation_error_payload(response.data)
        elif response.status_code in self.ERROR_PAYLOADS:
            response.data = self._build_error_payload(response.status_code)

        return response


@extend_schema(
    tags=["litters", "organizations_miots", "litters_new_profile"],
    description="API endpoint that allows litters to be viewed or edited."
)
class LitterViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    """
    LitterViewSet
    =============

    Endpoint tylko do odczytu zwracający listę miotów (*Litter*).
    Pozwala zawęzić wyniki do miotów określonej organizacji **lub** właściciela.

    Parametry zapytania
    -------------------
    - **organization-id** (int, opcjonalny)  
      ID organizacji. Jeżeli podany, zwracane są wyłącznie mioty
      przypisane do tej organizacji.

    - **user-id** (int, opcjonalny)  
      ID użytkownika–właściciela. Stosowany tylko wtedy, gdy
      `organization-id` nie został podany; zwraca mioty należące
      do wskazanego użytkownika.

    Zasady filtrowania
    ------------------
    1. Jeśli obecny jest `organization-id`, filtr ten ma **pierwszeństwo**.  
    2. W przeciwnym razie – jeśli podano `user-id` – zwracane są mioty
       danego użytkownika.  
    3. Brak obu parametrów zwraca wszystkie mioty w bazie.

    Przykłady
    ---------
    ```http
    # wszystkie mioty danej organizacji
    GET /litters/?organization-id=15

    # mioty konkretnego użytkownika (gdy brak organization-id)
    GET /litters/?user-id=42
    ```
    """
    
    queryset = Litter.objects.all()
    serializer_class = LitterSerializer
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
    description="API endpoint that allows litter‐animals to be viewed or edited."
)
class LitterAnimalViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    """
    API endpoint that allows litter‐animals to be viewed or edited.
    """
    queryset = LitterAnimal.objects.all()
    serializer_class = LitterAnimalSerializer
