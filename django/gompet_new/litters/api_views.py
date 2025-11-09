from django.utils.translation import gettext_lazy as _
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Litter, LitterAnimal
from .serializers import LitterSerializer, LitterAnimalSerializer


from drf_spectacular.utils import extend_schema
@extend_schema(
    tags=["litters", "organizations_miots", "litters_new_profile"],
    description="API endpoint that allows litters to be viewed."
)
class LitterViewSet(viewsets.ReadOnlyModelViewSet):
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
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = LitterSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        organization_param = self.request.query_params.get("organization-id")
        user_param = self.request.query_params.get("user-id")

        if organization_param:
            organization_id = self._parse_positive_int(organization_param, "organization-id")
            qs = qs.filter(organization_id=organization_id)
        elif user_param:
            user_id = self._parse_positive_int(user_param, "user-id")
            qs = qs.filter(owner_id=user_id)

        return qs

    @staticmethod
    def _parse_positive_int(value: str, param_name: str) -> int:
        try:
            parsed_value = int(value)
        except (TypeError, ValueError):
            raise ValidationError({param_name: _("Expected an integer value.")})

        if parsed_value < 1:
            raise ValidationError({param_name: _("Value must be greater than zero.")})

        return parsed_value


@extend_schema(
    tags=["litter-animals"],
    description="API endpoint that allows litter‐animals to be viewed or edited."
)
class LitterAnimalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows litter‐animals to be viewed or edited.
    """
    queryset = LitterAnimal.objects.all()
    serializer_class = LitterAnimalSerializer
