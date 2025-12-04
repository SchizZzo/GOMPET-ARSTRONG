from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import (
    TokenObtainPairView as SimpleJWTTokenObtainPairView,
    TokenRefreshView as SimpleJWTTokenRefreshView,
)

from .models import MemberRole, Organization, OrganizationMember, OrganizationType, Species, User
from .serializers import (
    OrganizationTypeSerializer, UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    OrganizationSerializer, OrganizationCreateSerializer, OrganizationUpdateSerializer,
    OrganizationMemberSerializer, OrganizationMemberCreateSerializer, LatestOrganizationSerializer, SpeciesSerializer
)
from .services import CannotDeleteUser, delete_user_account

@extend_schema(tags=["auth"])
class TokenCreateView(SimpleJWTTokenObtainPairView):
    """Endpoint do generowania pary tokenów JWT."""

    permission_classes = [permissions.AllowAny]


@extend_schema(tags=["auth"])
class TokenRefreshView(SimpleJWTTokenRefreshView):
    """Endpoint do odświeżania tokenu JWT."""

    permission_classes = [permissions.AllowAny]


@extend_schema(
    tags=["users", "users_figma"],
    description="API for managing users and organizations, including CRUD operations."
)
class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Users. 
    - list/retrieve: UserSerializer
    - create: UserCreateSerializer
    - update/partial_update: UserUpdateSerializer


    Dodaawanie użytkowników
    -------------------
    http://localhost/users/users/
    Metoda POST pozwala na rejestrację nowego użytkownika.
    Przykładowe dane wejściowe (JSON):
    {
        "first_name": "Nowy",
        "last_name": "Użytkownik",
        "email": "nowy_uzytkownik@example.com",
        "password": "supertajnehaslo"
    }


    """
    queryset = User.objects.filter(is_deleted=False)
    

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        if request.user != user and not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {"detail": "Nie masz uprawnień do usunięcia tego konta."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            delete_user_account(user)
        except CannotDeleteUser as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy_current(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            delete_user_account(request.user)
        except CannotDeleteUser as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK, data={
            "detail": "Konto zostało usunięte (dezaktywowane i zanonimizowane)."
        })


class DeleteMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        try:
            delete_user_account(request.user)
        except CannotDeleteUser as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Konto zostało usunięte (dezaktywowane i zanonimizowane)."},
            status=status.HTTP_200_OK,
        )

@extend_schema(
    tags=["organizations", "organizations_profile", "organizations_profile_pupils", "organizations_profile_miots", "organizations_new_profile"],
    description="API for managing organizations, including CRUD operations."
)
class OrganizationViewSet(viewsets.ModelViewSet):
    """
    OrganizationViewSet
    ===================

    Endpoint REST do zarządzania organizacjami (**Organization**).
    Umożliwia tworzenie organizacji oraz pobieranie ich danych.

    Dostępne metody HTTP
    --------------------
    - **GET /organizations/** – pobranie listy organizacji (wymaga uwierzytelnienia)  
    - **POST /organizations/** – utworzenie nowej organizacji, przypisując bieżącego użytkownika jako właściciela  
    - **GET /organizations/{id}/** – szczegóły konkretnej organizacji  
    - **PUT /organizations/{id}/**, **PATCH /organizations/{id}/** – aktualizacja danych  
    - **DELETE /organizations/{id}/** – usunięcie organizacji

    Uwagi dotyczące tworzenia (POST)
    --------------------------------
    - Podczas tworzenia organizacji (`POST`), bieżący użytkownik (`request.user`) zostaje automatycznie:
        • przypisany jako autor (`user` w modelu Organization)  
        • dodany jako członek organizacji z rolą `OWNER` w modelu `OrganizationMember`

    Wymagania
    ---------
    - Wszystkie operacje wymagają uwierzytelnienia (`IsAuthenticated`).

    Przykład
    --------
    ```http
    POST localhost/users/organizations/
    {

        "type": "SHELTER",
        
        "name": "Schronisko dla Zwierząt",
        "email": "kontakt@schronisko.pl",
        "address": {
            "street": "ul. Psia",
            "house_number": 1,
            "city": "Warszawa",

            "zip_code": "00-001",
            

            "lat": 52.229676, # współrzędne geograficzne (szerokość)
            "lng": 21.012229, # współrzędne geograficzne (długość)
            

            "location": {
                "type": "Point",
                "coordinates": [21.012229, 52.229676] # lng, lat
            }
        }
    }
    """
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    

    def perform_create(self, serializer):
        org = serializer.save(user=self.request.user)
        OrganizationMember.objects.create(
            user=self.request.user,
            organization=org,
            role=MemberRole.OWNER,
        )

    def get_queryset(self):
        qs = Organization.objects.all().order_by('-created_at')
        # filter by organization type

        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)

        # filtrowanie po zasięgu (parametr "zasieg" – wartość w metrach)
        zasieg_param = self.request.query_params.get('range')
        if zasieg_param:
            try:
                max_distance = float(zasieg_param)
                user_location = getattr(self.request.user, "location", None)
                print(f"User location: {user_location}, Max distance: {max_distance}")
                if user_location:
                    qs = (
                        qs.exclude(address__location__isnull=True)
                          .filter(
                              address__location__distance_lte=(
                                  user_location,
                                  D(m=max_distance)
                              )
                          )
                          .annotate(
                              distance=Distance("address__location", user_location)
                          )
                          .order_by("distance")
                    )
            except (TypeError, ValueError):
                pass

        city = self.request.query_params.get('city')
        if city:
            qs = qs.filter(address__city__iexact=city.strip())

         # filter by organization type

        org_type = self.request.query_params.get('organization-type')
        if org_type:
            org_types = [t.strip() for t in org_type.split(',') if t.strip()]
            qs = qs.filter(type__in=org_types)

        # filter by species
        species = self.request.query_params.get('species')
        if species:
            species_list = [s.strip() for s in species.split(',') if s.strip()]
            qs = qs.filter(species_organizations__species__name__in=species_list)

        breeding_type = self.request.query_params.get('breeding-type')
        if breeding_type:
            breeding_types = [bt.strip() for bt in breeding_type.split(',') if bt.strip()]
            qs = qs.filter(breeding_type_organizations__breeding_type__name__in=breeding_types)

        
        return qs

    

    


    

    # def get_serializer_class(self):
    #     if self.action == "create":
    #         return OrganizationCreateSerializer
    #     if self.action in ("update", "partial_update"):
    #         return OrganizationUpdateSerializer
    #     return OrganizationSerializer
    
@extend_schema(
    tags=["organizations_recently_added"],
)
class OrganizationRecentlyAddedViewSet(viewsets.ReadOnlyModelViewSet):
 
    """
    API do pobierania niedawno dodanych organizacji (tylko do odczytu).

    - list/retrieve: LatestOrganizationSerializer
    - parametry zapytania:
        * organization-type: filtrowanie po typie organizacji (lista rozdzielona przecinkami)
            - `SHELTER`: Schronisko / Fundacja
            - `BREEDER`: Hodowla
            - `CLINIC`: Gabinet weterynaryjny
            - `SHOP`: Sklep zoologiczny
            - `OTHER`: Inne
        * limit: maksymalna liczba wyników (domyślnie 10)

    Przykład zapytania:
    ```http
    GET /users/organizations-latest/?limit=20&organization-type=SHELTER
    ```
    """
    serializer_class = LatestOrganizationSerializer

    def get_queryset(self):
        qs = Organization.objects.all().order_by('-created_at')
        # filter by organization type
        org_type = self.request.query_params.get('organization-type')
        if org_type:
            org_types = [t.strip() for t in org_type.split(',') if t.strip()]
            qs = qs.filter(type__in=org_types)

        # apply limit parameter
        try:
            limit = int(self.request.query_params.get('limit', 10))
        except (TypeError, ValueError):
            limit = 10

        return qs[:limit]
    



@extend_schema(
    tags=["organization_members", "you_in_organization"],
    description="API for managing organization members, including CRUD operations."
)
class OrganizationMemberViewSet(viewsets.ModelViewSet):
    """
    CRUD API for OrganizationMember.
    - list/retrieve: OrganizationMemberSerializer
    - create: OrganizationMemberCreateSerializer
    - update/partial_update: OrganizationMemberCreateSerializer
    """
    queryset = OrganizationMember.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationMemberCreateSerializer
        if self.action in ("update", "partial_update"):
            return OrganizationMemberCreateSerializer
        return OrganizationMemberSerializer
    



@extend_schema(
    tags=["organizations_filtering"],
)
class OrganizationFilteringAddedViewSet(viewsets.ReadOnlyModelViewSet):
 
    """
    OrganizationFilteringAddedViewSet
    =================================

    Endpoint tylko do odczytu zwracający **najnowsze organizacje**  
    (posortowane malejąco po `created_at`) z rozbudowanym zestawem
    filtrów: typu organizacji, zasięgu, gatunków, typu hodowli i nazwy.

    Zwracany format
    ---------------
    - **list / retrieve**: `LatestOrganizationSerializer`

    Parametry zapytania
    -------------------
    - **name** (str, opcjonalny)  
      Fragment nazwy organizacji (niewrażliwy na wielkość liter).

    - **organization-type** (str, opcjonalny)  
      Jeden lub więcej typów organizacji (przecinkami):  
        • `SHELTER` – Schronisko / Fundacja  
        • `BREEDER` – Hodowla  
        • `CLINIC`  – Gabinet weterynaryjny  
        • `SHOP`    – Sklep zoologiczny  
        • `OTHER`   – Inne

    - **range** (float, opcjonalny)  
      Maksymalna odległość w **metrach** od lokalizacji użytkownika  
      (`User.location`). Wyniki są wtedy sortowane rosnąco według
      odległości. Jeśli użytkownik nie ma ustawionej lokalizacji,
      parametr jest ignorowany.

    - **breeding-type** (str, opcjonalny)  
      Jeden lub więcej typów hodowli (przecinkami). Dozwolone kody:  

        | Kod          | Opis                         |
        |--------------|------------------------------|
        | `pet`        | Towarzyska / domowa          |
        | `poultry`    | Drób                         |
        | `cattle`     | Bydło                        |
        | `swine`      | Trzoda chlewna               |
        | `fur`        | Futerkowa                    |
        | `aquaculture`| Akwakultura                  |
        | `apiculture` | Pszczelarstwo                |
        | `laboratory` | Laboratoryjna                |
        | `conservation`| Konserwatorska             |
        | `other`      | Inna                         |

    - **species** (str, opcjonalny)  
      Gatunki zwierząt obsługiwane przez organizację (przecinkami):  
        • `dog` – Pies  
        • `cat` – Kot  
        • `rabbit` – Królik  
        • `hamster` – Chomik  
        • `bird` – Ptak  
        • `reptile` – Gad  
        • `fish` – Ryba  
        • `other` – Inne

    Zasady filtrowania
    ------------------
    1. Wszystkie podane parametry łączone są operatorem **AND**.  
    2. `range` uwzględnia tylko organizacje z nie-pustym polem
       `address.location`.  
    3. Brak parametrów ⇒ zwracane są wszystkie organizacje w kolejności
       od najnowszych.

    Przykład
    --------
    ```http
    GET /users/organization-filtering/?
        organization-type=SHELTER,CLINIC
        &range=10000
        &breeding-type=poultry,cattle
        &species=dog,cat
        &name=centrum
    ```
    Zwraca najnowsze schroniska lub kliniki zawierające w nazwie
    „centrum”, prowadzące hodowlę drobiu lub bydła, obsługujące psy lub
    koty, oddalone nie więcej niż 10 km od użytkownika.
    """
    serializer_class = LatestOrganizationSerializer

    def get_queryset(self):
        qs = Organization.objects.all().order_by('-created_at')
        # filter by organization type

        name = self.request.query_params.get("name")
        if name:
            qs = qs.filter(name__icontains=name)

        zasieg_param = self.request.query_params.get("range")
        if zasieg_param:
            try:
                max_distance = float(zasieg_param)
                user_location = getattr(self.request.user, "location", None)
                if user_location:
                    qs = (
                    qs.exclude(address__location__isnull=True)
                    .filter(
                        address__location__distance_lte=(
                        user_location,
                        D(m=max_distance)
                        )
                    )
                    .annotate(
                        distance=Distance("address__location", user_location)
                    )
                    .order_by("distance")
                    )
            except (TypeError, ValueError):
                pass

        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(address__city__iexact=city.strip())

        org_type = self.request.query_params.get("organization-type")
        if org_type:
            org_types = [t.strip().upper() for t in org_type.split(",") if t.strip()]
            qs = qs.filter(type__in=org_types)

        species = self.request.query_params.get("species")
        if species:
            species_list = [s.strip() for s in species.split(",") if s.strip()]
            qs = qs.filter(species_organizations__species__name__in=species_list)

        breeding_type = self.request.query_params.get("breeding-type")
        if breeding_type:
            breeding_types = [bt.strip() for bt in breeding_type.split(",") if bt.strip()]
            qs = qs.filter(breeding_type_organizations__breeding_type__name__in=breeding_types)

        return qs.distinct()
    

@extend_schema(
    tags=["species", "species_miots"],
    description="API endpoint that allows species to be viewed."
)
class SpeciesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows species to be viewed.
    """
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]




class OrganizationTypeListView(viewsets.ViewSet):
    """Zwraca listę dostępnych typów organizacji (code + label)."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def list(self, request):
        serializer = OrganizationTypeSerializer(
            OrganizationTypeSerializer.get_choices(), many=True
        )
        return Response(serializer.data)
