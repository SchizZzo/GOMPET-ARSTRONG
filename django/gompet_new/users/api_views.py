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

from common.models import Notification
from common.notifications import broadcast_user_notification, build_notification_payload
from .models import Address, MemberRole, Organization, OrganizationMember, OrganizationType, Species, User
from .serializers import (
    OrganizationTypeSerializer, UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    OrganizationSerializer, OrganizationCreateSerializer, OrganizationUpdateSerializer,
    OrganizationMemberSerializer, OrganizationMemberCreateSerializer, LatestOrganizationSerializer, SpeciesSerializer,
    OrganizationAddressSerializer,
)
from .services import CannotDeleteUser, delete_user_account
from .role_permissions import sync_user_member_role_groups

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
        if self.action in ("update", "partial_update", "update_current"):
            return UserUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        if request.user != user and not request.user.has_perm("users.delete_user"):
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

    def update_current(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        partial = request.method.lower() == "patch"
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


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
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]


    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        if self.action in {"update", "partial_update"}:
            return OrganizationUpdateSerializer
        return super().get_serializer_class()

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = False
        return self._update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self._update(request, *args, **kwargs)

    def _update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    

    def perform_create(self, serializer):
        org = serializer.save(user=self.request.user)
        OrganizationMember.objects.create(
            user=self.request.user,
            organization=org,
            role=MemberRole.OWNER,
        )
        sync_user_member_role_groups(self.request.user)
        

    def get_queryset(self):
        qs = Organization.objects.all().order_by('-created_at')
        user_location = (
            getattr(self.request.user, "location", None)
            if self.request.user and self.request.user.is_authenticated
            else None
        )

        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)

        # filtrowanie po zasięgu (parametr "zasieg" – wartość w metrach)
        zasieg_param = self.request.query_params.get('range')
        if user_location:
            qs = qs.exclude(address__location__isnull=True).annotate(
                distance=Distance("address__location", user_location)
            )

            if zasieg_param:
                try:
                    max_distance = float(zasieg_param)
                    qs = qs.filter(
                        address__location__distance_lte=(user_location, D(m=max_distance))
                    )
                except (TypeError, ValueError):
                    pass

            qs = qs.order_by("distance")
        elif zasieg_param:
            # brak lokalizacji użytkownika – ignorujemy parametr zasięgu
            try:
                float(zasieg_param)
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

    def get_queryset(self):
        queryset = OrganizationMember.objects.all()
        only_mine = self.request.query_params.get("mine")
        if only_mine and only_mine.lower() in ("1", "true", "yes"):
            queryset = queryset.filter(user=self.request.user, role = MemberRole.OWNER or MemberRole.STAFF)

        organization_id = self.request.query_params.get("organization-id")
        if organization_id:
            queryset = queryset.filter(organization_id=organization_id)

        organization_id_confirmed = self.request.query_params.get("organization-id-confirmed")
        if organization_id_confirmed:
            queryset = queryset.filter(organization_id=organization_id_confirmed, invitation_confirmed=True)
        
        return queryset
    


    def perform_create(self, serializer):
        member = serializer.save()
        sync_user_member_role_groups(member.user)
        organization = member.organization
        owner = organization.user if organization else None
        if not owner or owner.id == self.request.user.id:
            return

        notification = Notification.objects.create(
            recipient=owner,
            actor=self.request.user,
            verb="wysłał(a) zaproszenie do organizacji",
            target_type="organization",
            target_id=organization.id,
            created_object_id=member.id,
        )
        broadcast_user_notification(
            owner.id, build_notification_payload(notification)
        )

    def perform_update(self, serializer):
        member = serializer.save()
        sync_user_member_role_groups(member.user)
    



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
        user_location = (
            getattr(self.request.user, "location", None)
            if self.request.user and self.request.user.is_authenticated
            else None
        )

        name = self.request.query_params.get("name")
        if name:
            qs = qs.filter(name__icontains=name)

        zasieg_param = self.request.query_params.get("range")
        if user_location:
            qs = qs.exclude(address__location__isnull=True).annotate(
                distance=Distance("address__location", user_location)
            )

            if zasieg_param:
                try:
                    max_distance = float(zasieg_param)
                    qs = qs.filter(
                        address__location__distance_lte=(user_location, D(m=max_distance))
                    )
                except (TypeError, ValueError):
                    pass

            qs = qs.order_by("distance")
        elif zasieg_param:
            # brak lokalizacji użytkownika – ignorujemy parametr zasięgu
            try:
                float(zasieg_param)
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
    


@extend_schema(tags=["organization_addresses"])
class OrganizationAddressViewSet(viewsets.ReadOnlyModelViewSet):
    """Endpoint do odczytu adresów organizacji."""

    queryset = Address.objects.select_related("organization").prefetch_related("species")
    serializer_class = OrganizationAddressSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = super().get_queryset()

        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city.strip())

        org_type = self.request.query_params.get("organization-type")
        if org_type:
            org_types = [t.strip() for t in org_type.split(",") if t.strip()]
            qs = qs.filter(organization__type__in=org_types)

        return qs


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
