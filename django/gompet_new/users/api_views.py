import logging

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
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
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from common.models import Notification
from common.notifications import broadcast_user_notification, build_notification_payload
from .models import Address, MemberRole, Organization, OrganizationMember, OrganizationType, Species, User
from .serializers import (
    OrganizationTypeSerializer, MemberRoleSerializer, UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    OrganizationSerializer, OrganizationCreateSerializer, OrganizationUpdateSerializer,
    OrganizationMemberSerializer, OrganizationMemberCreateSerializer, LatestOrganizationSerializer, SpeciesSerializer,
    OrganizationAddressSerializer, OrganizationOwnerChangeSerializer, ProfileInfoSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
)
from .permissions import OrganizationRolePermissions
from .services import CannotDeleteUser, delete_user_account, transfer_organization_owner
from .role_permissions import sync_user_member_role_groups, sync_user_role_groups

logger = logging.getLogger(__name__)

class TokenCreateSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = getattr(self, "user", None)
        if user:
            sync_user_member_role_groups(user)
            sync_user_role_groups(user)
            data["permissions"] = sorted(user.get_all_permissions())
        return data

@extend_schema(tags=["auth"])
class TokenCreateView(SimpleJWTTokenObtainPairView):
    """Endpoint do generowania pary tokenów JWT."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TokenCreateSerializer


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
        if self.action in ("create", "profile_info"):
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

    @action(
        detail=True,
        methods=["get"],
        url_path="profile-info",
        permission_classes=[permissions.AllowAny],
    )
    def profile_info(self, request, *args, **kwargs):
        user = self.get_object()
        memberships = (
            OrganizationMember.objects.filter(user=user)
            .select_related("organization", "user")
        )
        serializer = ProfileInfoSerializer(
            {"user": user, "memberships": memberships}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


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


@extend_schema(tags=["auth"])
class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email, is_deleted=False).first()
        if user and user.is_active:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_PASSWORD_RESET_URL}?uid={uid}&token={token}"

            try:
                send_mail(
                    subject="Reset hasła",
                    message=(
                        "Otrzymaliśmy prośbę o reset hasła.\n"
                        f"Aby ustawić nowe hasło, przejdź do: {reset_url}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Nie udało się wysłać maila resetu hasła.")
                return Response(
                    {"detail": "Nie udało się wysłać maila resetu hasła."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {"detail": "Jeśli konto istnieje, wysłaliśmy instrukcje resetu hasła."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["auth"])
class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
        except (TypeError, ValueError, OverflowError):
            user_id = None

        user = User.objects.filter(pk=user_id, is_deleted=False).first()
        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Nieprawidłowy lub wygasły token resetu hasła."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Hasło zostało zresetowane."},
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
    permission_classes = [IsAuthenticatedOrReadOnly, OrganizationRolePermissions]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]


    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        if self.action in {"update", "partial_update"}:
            return OrganizationUpdateSerializer
        return super().get_serializer_class()

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
        serializer.save(user=self.request.user)
        

    @action(detail=True, methods=["post"], url_path="change-owner")
    def change_owner(self, request, pk=None):
        organization = self.get_object()
        if not request.user.is_superuser and organization.user_id != request.user.id:
            return Response(
                {"detail": "Tylko właściciel organizacji może zmienić właściciela."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = OrganizationOwnerChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_owner = serializer.validated_data["user"]
        transfer_organization_owner(organization, new_owner)

        response_serializer = OrganizationSerializer(organization, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

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

        org_user_id = self.request.query_params.get('user-id')
        if org_user_id:
            qs = qs.filter(user__id=org_user_id)

        
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
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationMemberCreateSerializer
        if self.action in ("update", "partial_update"):
            return OrganizationMemberCreateSerializer
        return OrganizationMemberSerializer

    def get_queryset(self):
        queryset = OrganizationMember.objects.all()
        user = self.request.user
        if not user or not user.is_authenticated:
            return queryset.none()
        if not user.is_superuser:
            queryset = queryset.filter(organization__members__user=user).distinct()

        only_mine = self.request.query_params.get("mine")
        if only_mine and only_mine.lower() in ("1", "true", "yes"):
            queryset = queryset.filter(
                user=self.request.user,
                #role__in=[MemberRole.OWNER, MemberRole.STAFF],
            )

        organizations_user_by_id = self.request.query_params.get("organizations-user-by-id")
        if organizations_user_by_id:
            queryset = queryset.filter(
                organization__user__id=organizations_user_by_id
            )


        organization_id = self.request.query_params.get("organization-id")
        if organization_id:
            is_owner = OrganizationMember.objects.filter(
                organization_id=organization_id,
                user=user,
                role=MemberRole.OWNER,
                
            ).exists()
            if not is_owner:
                return queryset.none()
            queryset = queryset.filter(organization_id=organization_id, invitation_confirmed=False)

        organization_id_confirmed = self.request.query_params.get("organization-id-confirmed")
        if organization_id_confirmed:
            is_owner = OrganizationMember.objects.filter(
                organization_id=organization_id_confirmed,
                user=user,
                role=MemberRole.OWNER,
            ).exists()
            if not is_owner:
                return queryset.none()
            queryset = queryset.filter(organization_id=organization_id_confirmed, invitation_confirmed=True)

        organization_member_user_id = self.request.query_params.get("organization-member-user-id")
        if organization_member_user_id:
            queryset = queryset.filter(user__id=organization_member_user_id)
        
        return queryset
    


    def perform_create(self, serializer):
        member = serializer.save()
        sync_user_member_role_groups(member.user)
        sync_user_role_groups(member.user)
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
        member = self.get_object()
        was_confirmed = member.invitation_confirmed
        member = serializer.save()
        sync_user_member_role_groups(member.user)
        sync_user_role_groups(member.user)
        if not was_confirmed and member.invitation_confirmed:
            organization = member.organization
            owner = organization.user if organization else None
            if owner and owner.id != self.request.user.id:
                notification = Notification.objects.create(
                    recipient=owner,
                    actor=self.request.user,
                    verb="potwierdził(a) zaproszenie do organizacji",
                    target_type="organization",
                    target_id=organization.id,
                    created_object_id=member.id,
                )
                broadcast_user_notification(
                    owner.id, build_notification_payload(notification)
                )

            if owner and owner.id == self.request.user.id and member.user:
                notification = Notification.objects.create(
                    recipient=member.user,
                    actor=self.request.user,
                    verb="przyjął(a) Cię do organizacji",
                    target_type="organization",
                    target_id=organization.id,
                    created_object_id=member.id,
                )
                broadcast_user_notification(
                    member.user.id, build_notification_payload(notification)
                )

    def perform_destroy(self, instance):
        member = instance
        organization = member.organization
        recipient = member.user
        if recipient and recipient.id != self.request.user.id:
            notification = Notification.objects.create(
                recipient=recipient,
                actor=self.request.user,
                verb="usunął(a) Cię z organizacji",
                target_type="organization",
                target_id=organization.id,
                created_object_id=member.id,
            )
            broadcast_user_notification(
                recipient.id, build_notification_payload(notification)
            )
        member.delete()
    



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


class OrganizationMemberRoleListView(viewsets.ViewSet):
    """Zwraca listę dostępnych ról członków organizacji (code + label)."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    def list(self, request):
        serializer = MemberRoleSerializer(
            MemberRoleSerializer.get_choices(), many=True
        )
        return Response({"roles": serializer.data})
