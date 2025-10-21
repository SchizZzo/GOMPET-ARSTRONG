from rest_framework import viewsets
from .models import Litter, LitterAnimal
from .serializers import LitterSerializer, LitterAnimalSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly


from drf_spectacular.utils import extend_schema
@extend_schema(
    tags=["litters", "organizations_miots", "litters_new_profile"],
    description="API endpoint that allows litters to be viewed or edited."
)
class LitterViewSet(viewsets.ModelViewSet):
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
    permission_classes = [IsAuthenticatedOrReadOnly]  # AllowAny
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
class LitterAnimalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows litter‐animals to be viewed or edited.
    """
    queryset = LitterAnimal.objects.all()
    serializer_class = LitterAnimalSerializer