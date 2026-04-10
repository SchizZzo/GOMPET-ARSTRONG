import logging

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from django.db.models import Q
from rest_framework import permissions, serializers, status, viewsets
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
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity

logger = logging.getLogger(__name__)


ORGANIZATION_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="name",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Organization name fragment (case-insensitive).",
    ),
    OpenApiParameter(
        name="range",
        type=float,
        location=OpenApiParameter.QUERY,
        description="Maximum distance in meters from current user location.",
    ),
    OpenApiParameter(
        name="city",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Exact city name.",
    ),
    OpenApiParameter(
        name="organization-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated organization types.",
    ),
    OpenApiParameter(
        name="species",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated species names from organization address.",
    ),
    OpenApiParameter(
        name="species-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Alias for species (comma-separated) from organization address.",
    ),
    OpenApiParameter(
        name="breeding-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated breeding type names.",
    ),
    OpenApiParameter(
        name="user-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter organizations by owner user ID.",
    ),
]

ORGANIZATION_RECENT_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="organization-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated organization types.",
    ),
    OpenApiParameter(
        name="limit",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Maximum number of returned organizations (default: 10).",
    ),
]

ORGANIZATION_MEMBER_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="mine",
        type=bool,
        location=OpenApiParameter.QUERY,
        description="Set to true to return memberships of current user.",
    ),
    OpenApiParameter(
        name="organizations-user-by-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter by organization owner user ID.",
    ),
    OpenApiParameter(
        name="organization-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Pending invitations for selected organization ID.",
    ),
    OpenApiParameter(
        name="organization-id-confirmed",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Confirmed memberships for selected organization ID.",
    ),
    OpenApiParameter(
        name="organization-member-user-id",
        type=int,
        location=OpenApiParameter.QUERY,
        description="Filter memberships by member user ID.",
    ),
]

ORGANIZATION_FILTERING_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="name",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Organization name fragment.",
    ),
    OpenApiParameter(
        name="range",
        type=float,
        location=OpenApiParameter.QUERY,
        description="Maximum distance in meters from current user location.",
    ),
    OpenApiParameter(
        name="city",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Exact city name.",
    ),
    OpenApiParameter(
        name="organization-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated organization types.",
    ),
    OpenApiParameter(
        name="species",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated species names from organization address.",
    ),
    OpenApiParameter(
        name="species-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Alias for species (comma-separated) from organization address.",
    ),
    OpenApiParameter(
        name="breeding-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated breeding type names.",
    ),
]

ORGANIZATION_ADDRESS_LIST_FILTER_PARAMETERS = [
    OpenApiParameter(
        name="city",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Exact city name.",
    ),
    OpenApiParameter(
        name="organization-type",
        type=str,
        location=OpenApiParameter.QUERY,
        description="Comma-separated organization types.",
    ),
]


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

    def validation_error_response(self, errors):
        return Response(
            self._build_validation_error_payload(errors),
            status=status.HTTP_400_BAD_REQUEST,
        )

    def unauthorized_response(self):
        return Response(
            self._build_error_payload(status.HTTP_401_UNAUTHORIZED),
            status=status.HTTP_401_UNAUTHORIZED,
        )

    def forbidden_response(self):
        return Response(
            self._build_error_payload(status.HTTP_403_FORBIDDEN),
            status=status.HTTP_403_FORBIDDEN,
        )

    def server_error_response(self):
        return Response(
            self._build_error_payload(status.HTTP_500_INTERNAL_SERVER_ERROR),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )



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
class TokenCreateView(StandardizedErrorResponseMixin, SimpleJWTTokenObtainPairView):
    """Endpoint do generowania pary tokenów JWT."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TokenCreateSerializer


@extend_schema(tags=["auth"])
class TokenRefreshView(StandardizedErrorResponseMixin, SimpleJWTTokenRefreshView):
    """Endpoint do odświeżania tokenu JWT."""

    permission_classes = [permissions.AllowAny]


@extend_schema(
    tags=["users", "users_figma"],
    description="API for managing users and organizations, including CRUD operations."
)
class UserViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
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

    @staticmethod
    def _can_manage_user(actor, target) -> bool:
        if not actor or not actor.is_authenticated:
            return False
        return actor.is_superuser or actor.id == target.id

    @extend_schema(
        operation_id="users_users_update_by_id",
        summary="Zastap uzytkownika po ID",
        request=UserUpdateSerializer,
        responses=UserSerializer,
    )
    def update(self, request, *args, **kwargs):
        user = self.get_object()
        if not self._can_manage_user(request.user, user):
            return self.forbidden_response()
        return super().update(request, *args, **kwargs)

    @extend_schema(
        operation_id="users_users_partial_update_by_id",
        summary="Czesciowo zaktualizuj uzytkownika po ID",
        request=UserUpdateSerializer,
        responses=UserSerializer,
    )
    def partial_update(self, request, *args, **kwargs):
        user = self.get_object()
        if not self._can_manage_user(request.user, user):
            return self.forbidden_response()
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        operation_id="users_users_destroy_by_id",
        summary="Usun uzytkownika po ID",
    )
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        if not self._can_manage_user(request.user, user):
            return self.forbidden_response()

        try:
            delete_user_account(user)
        except CannotDeleteUser as exc:
            return self.validation_error_response({"detail": str(exc)})

        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy_current(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.unauthorized_response()

        try:
            delete_user_account(request.user)
        except CannotDeleteUser as exc:
            return self.validation_error_response({"detail": str(exc)})

        return Response(status=status.HTTP_200_OK, data={
            "detail": "Konto zostało usunięte (dezaktywowane i zanonimizowane)."
        })

    def update_current(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.unauthorized_response()

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


class DeleteMeView(StandardizedErrorResponseMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["users"],
        summary="Usuń własne konto",
        description="Usuwa (dezaktywuje i anonimizuje) aktualnie zalogowane konto użytkownika.",
        responses={
            200: inline_serializer(
                name="DeleteMeSuccessResponse",
                fields={"detail": serializers.CharField()},
            )
        },
    )
    def delete(self, request):
        try:
            delete_user_account(request.user)
        except CannotDeleteUser as exc:
            return self.validation_error_response({"detail": str(exc)})

        return Response(
            {"detail": "Konto zostało usunięte (dezaktywowane i zanonimizowane)."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["auth"])
class PasswordResetRequestView(StandardizedErrorResponseMixin, APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Poproś o reset hasła",
        request=PasswordResetRequestSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetRequestResponse",
                fields={"detail": serializers.CharField()},
            )
        },
    )
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
                return self.server_error_response()

        return Response(
            {"detail": "Jeśli konto istnieje, wysłaliśmy instrukcje resetu hasła."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["auth"])
class PasswordResetConfirmView(StandardizedErrorResponseMixin, APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Ustaw nowe hasło",
        request=PasswordResetConfirmSerializer,
        responses={
            200: inline_serializer(
                name="PasswordResetConfirmResponse",
                fields={"detail": serializers.CharField()},
            )
        },
    )
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
            return self.validation_error_response(
                {"detail": "Nieprawidłowy lub wygasły token resetu hasła."}
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
@extend_schema_view(
    list=extend_schema(
        summary="Lista organizacji z filtrami",
        description="Udostepnia filtry query dla listy organizacji w Swagger UI.",
        parameters=ORGANIZATION_LIST_FILTER_PARAMETERS,
    )
)
class OrganizationViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
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
            return self.forbidden_response()

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
            qs = qs.annotate(
            similarity=TrigramSimilarity('name', name)
            ).filter(
            similarity__gt=0.1
            ).order_by('-similarity')

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
            species_query = Q()
            for value in species_list:
                species_query |= Q(address__species__name__iexact=value)
                species_query |= Q(address__species__label__iexact=value)
            qs = qs.filter(species_query).distinct()

        breeding_type = self.request.query_params.get('breeding-type')
        if breeding_type:
            breeding_types = [bt.strip() for bt in breeding_type.split(',') if bt.strip()]
            qs = qs.filter(breeding_type_organizations__breeding_type__name__in=breeding_types)


        species_type = self.request.query_params.get('species-type')
        if species_type:
            species_types = [st.strip() for st in species_type.split(',') if st.strip()]
            species_type_query = Q()
            for value in species_types:
                species_type_query |= Q(address__species__name__iexact=value)
                species_type_query |= Q(address__species__label__iexact=value)
            qs = qs.filter(species_type_query).distinct()

         # filter by owner user ID

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
@extend_schema_view(
    list=extend_schema(
        summary="Najnowsze organizacje z filtrami",
        description="Udostepnia filtry query dla listy najnowszych organizacji.",
        parameters=ORGANIZATION_RECENT_LIST_FILTER_PARAMETERS,
    )
)
class OrganizationRecentlyAddedViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
 
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
@extend_schema_view(
    list=extend_schema(
        summary="Lista czlonkow organizacji z filtrami",
        description="Udostepnia filtry query dla listy czlonkow organizacji.",
        parameters=ORGANIZATION_MEMBER_LIST_FILTER_PARAMETERS,
    )
)
class OrganizationMemberViewSet(StandardizedErrorResponseMixin, viewsets.ModelViewSet):
    """
    CRUD API for OrganizationMember.
    - list/retrieve: OrganizationMemberSerializer
    - create: OrganizationMemberCreateSerializer
    - update/partial_update: OrganizationMemberCreateSerializer
    """
    queryset = OrganizationMember.objects.all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _is_truthy(value) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _is_organization_owner(self, organization_id: int) -> bool:
        user = self.request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return OrganizationMember.objects.filter(
            organization_id=organization_id,
            user=user,
            role=MemberRole.OWNER,
            invitation_confirmed=True,
        ).exists()

    def _is_self_confirmation_request(self, membership: OrganizationMember) -> bool:
        if membership.user_id != self.request.user.id:
            return False

        payload_keys = set(self.request.data.keys())
        if not payload_keys or not payload_keys.issubset({"invitation_confirmed"}):
            return False

        return self._is_truthy(self.request.data.get("invitation_confirmed"))

    def _can_update_membership(self, membership: OrganizationMember) -> bool:
        if self._is_organization_owner(membership.organization_id):
            return True
        return self._is_self_confirmation_request(membership)

    def _can_delete_membership(self, membership: OrganizationMember) -> bool:
        if self._is_organization_owner(membership.organization_id):
            return True
        return membership.user_id == self.request.user.id

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationMemberCreateSerializer
        if self.action in ("update", "partial_update"):
            return OrganizationMemberCreateSerializer
        return OrganizationMemberSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.validated_data.get("organization")
        if organization is None:
            return self.forbidden_response()

        is_owner = self._is_organization_owner(organization.id)
        if not is_owner:
            requested_user = serializer.validated_data.get("user")
            if requested_user is None or requested_user.id != request.user.id:
                return self.forbidden_response()

            requested_role = serializer.validated_data.get("role")
            if requested_role == MemberRole.OWNER:
                return self.forbidden_response()

            # Non-owner can only create their own join request.
            serializer.validated_data["invitation_confirmed"] = False

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        membership = self.get_object()
        if not self._can_update_membership(membership):
            return self.forbidden_response()
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        membership = self.get_object()
        if not self._can_update_membership(membership):
            return self.forbidden_response()
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if not self._can_delete_membership(membership):
            return self.forbidden_response()
        return super().destroy(request, *args, **kwargs)

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
    tags=["organization_members", "you_in_organization"],
    summary="Sprawdz czlonkostwo w organizacji",
    description=(
        "Sprawdza, czy aktualnie zalogowany uzytkownik (`request.user`) "
        "jest czlonkiem wskazanej organizacji. "
        "Nie wymaga parametru `user_id` w query."
    ),
)
class OrganizationMembershipCheckView(StandardizedErrorResponseMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="users_organization_check_membership",
        responses={
            200: inline_serializer(
                name="OrganizationMembershipCheckResponse",
                fields={
                    "organization_id": serializers.IntegerField(),
                    "user_id": serializers.IntegerField(),
                    "is_member": serializers.BooleanField(),
                    "membership_id": serializers.IntegerField(allow_null=True),
                    "role": serializers.CharField(allow_null=True),
                    "invitation_confirmed": serializers.BooleanField(allow_null=True),
                },
            )
        },
    )
    def get(self, request, organization_id: int):
        membership = (
            OrganizationMember.objects.filter(
                organization_id=organization_id,
                user=request.user,
            )
            .order_by("-invitation_confirmed", "id")
            .first()
        )

        if not membership:
            return Response(
                {
                    "organization_id": organization_id,
                    "user_id": request.user.id,
                    "is_member": False,
                    "membership_id": None,
                    "role": None,
                    "invitation_confirmed": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "organization_id": organization_id,
                "user_id": request.user.id,
                "is_member": True,
                "membership_id": membership.id,
                "role": membership.role,
                "invitation_confirmed": membership.invitation_confirmed,
            },
            status=status.HTTP_200_OK,
        )




@extend_schema(
    tags=["organizations_filtering"],
)
@extend_schema_view(
    list=extend_schema(
        summary="Filtrowanie organizacji",
        description="Udostepnia filtry query dla endpointu organization-filtering.",
        parameters=ORGANIZATION_FILTERING_LIST_FILTER_PARAMETERS,
    )
)
class OrganizationFilteringAddedViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
 
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
            species_query = Q()
            for value in species_list:
                species_query |= Q(address__species__name__iexact=value)
                species_query |= Q(address__species__label__iexact=value)
            qs = qs.filter(species_query)

        species_type = self.request.query_params.get("species-type")
        if species_type:
            species_type_list = [s.strip() for s in species_type.split(",") if s.strip()]
            species_type_query = Q()
            for value in species_type_list:
                species_type_query |= Q(address__species__name__iexact=value)
                species_type_query |= Q(address__species__label__iexact=value)
            qs = qs.filter(species_type_query)

        breeding_type = self.request.query_params.get("breeding-type")
        if breeding_type:
            breeding_types = [bt.strip() for bt in breeding_type.split(",") if bt.strip()]
            qs = qs.filter(breeding_type_organizations__breeding_type__name__in=breeding_types)

        return qs.distinct()
    


@extend_schema(tags=["organization_addresses"])
@extend_schema_view(
    list=extend_schema(
        summary="Lista adresow organizacji z filtrami",
        description="Udostepnia filtry query dla listy adresow organizacji.",
        parameters=ORGANIZATION_ADDRESS_LIST_FILTER_PARAMETERS,
    )
)
class OrganizationAddressViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
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
class SpeciesViewSet(StandardizedErrorResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows species to be viewed.
    """
    queryset = Species.objects.all()
    serializer_class = SpeciesSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]




class OrganizationTypeListView(StandardizedErrorResponseMixin, viewsets.ViewSet):
    """Zwraca listę dostępnych typów organizacji (code + label)."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=["organizations"],
        summary="Lista typów organizacji",
        responses=OrganizationTypeSerializer(many=True),
    )
    def list(self, request):
        serializer = OrganizationTypeSerializer(
            OrganizationTypeSerializer.get_choices(), many=True
        )
        return Response(serializer.data)


class OrganizationMemberRoleListView(StandardizedErrorResponseMixin, viewsets.ViewSet):
    """Zwraca listę dostępnych ról członków organizacji (code + label)."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        tags=["organization_members"],
        summary="Lista ról członka organizacji",
        responses=inline_serializer(
            name="OrganizationMemberRoleListResponse",
            fields={"roles": MemberRoleSerializer(many=True)},
        ),
    )
    def list(self, request):
        serializer = MemberRoleSerializer(
            MemberRoleSerializer.get_choices(), many=True
        )
        return Response({"roles": serializer.data})
