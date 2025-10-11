from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Post
from .serializers import PostSerializer

# posts/api_views.py

from drf_spectacular.utils import extend_schema

@extend_schema(
    tags=["posts", "posts_organizations", "posts_animals"],
    description="API endpoint to list and create posts."
)
class PostViewSet(viewsets.ModelViewSet):
    """
    PostViewSet
    ===========

    Endpoint REST do pobierania i zarządzania postami (obiekty **Post**).

    Dostępne metody HTTP
    --------------------
    - **GET /posts/** – lista postów z możliwością filtrowania  
    - **POST /posts/** – utworzenie nowego postu  
    - **GET /posts/{id}/** – szczegóły pojedynczego postu  
    - **PUT /posts/{id}/**, **PATCH /posts/{id}/** – aktualizacja  
    - **DELETE /posts/{id}/** – usunięcie

    Parametry zapytania (lista)
    ---------------------------
    - **animal-id** (int, opcjonalny)  
      ID zwierzęcia; zwraca posty powiązane z danym zwierzęciem
      (`Post.animal_id`).

    - **organization-id** (int, opcjonalny)  
      ID organizacji; zwraca posty dotyczące wskazanej organizacji
      (`Post.organization_id`).

    Zasady filtrowania
    ------------------
    - Jeżeli podasz **oba** parametry, rezultaty muszą spełniać *oba*
      warunki (operator AND).  
    - Brak parametrów → zwracane są wszystkie posty.

    Przykłady
    ---------
    ```http
    # Posty dla zwierzęcia o ID 17
    GET /posts/?animal-id=17

    # Posty organizacji 5
    GET /posts/?organization-id=5

    # Posty zwierzęcia 17 w organizacji 5
    GET /posts/?animal-id=17&organization-id=5
    ```


    Aktualizacja postu 

    PUT posts/posts/{id}/
    -----------------
    z danymi:
    {
    "content": "NOWY POST"
    }



    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ] # Każdy może czytać, ale tworzyć/edytować tylko zalogowani

    def _ensure_user_can_modify_animal(self, serializer):
        animal = serializer.validated_data.get("animal")
        if animal is None and getattr(serializer, "instance", None) is not None:
            animal = serializer.instance.animal

        if (
            animal
            and not self.request.user.is_staff
            and animal.owner_id != self.request.user.id
        ):
            raise PermissionDenied(
                "Tylko właściciel zwierzęcia lub administrator może modyfikować post."
            )

    def perform_create(self, serializer):
        self._ensure_user_can_modify_animal(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._ensure_user_can_modify_animal(serializer)
        serializer.save()

    def get_queryset(self):
        qs = super().get_queryset()
        animal_id = self.request.query_params.get("animal-id")
        organization_id = self.request.query_params.get("organization-id")
        if animal_id:
            qs = qs.filter(animal_id=animal_id)
        if organization_id:
            qs = qs.filter(organization_id=organization_id)
        return qs

    def perform_destroy(self, instance):
        user = self.request.user
        if not user.is_staff and instance.author_id != user.id:
            raise PermissionDenied(
                "Tylko autor posta lub administrator może go usunąć."
            )
        super().perform_destroy(instance)


