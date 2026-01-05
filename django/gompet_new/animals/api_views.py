from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import (
    Animal,
    AnimalCharacteristic,
    AnimalGallery,
    AnimalParent,
    Characteristics,
    AnimalsBreedGroups,
    
)


from .serializers import (
    AnimalSerializer,
    AnimalCharacteristicSerializer,
    AnimalGallerySerializer,
    AnimalParentSerializer,
    RecentlyAddedAnimalSerializer,
    CharacteristicsSerializer,
    AnimalsBreedGroupsSerializer,

    
)
from drf_spectacular.utils import extend_schema
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework import serializers
from datetime import date
from dateutil.relativedelta import relativedelta
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from django.db.models import Q
import json
from django.core.exceptions import FieldError
from common.models import Reaction, ReactionType

class FamilyTreeNodeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    parents = serializers.ListField(child=serializers.DictField())
    children = serializers.ListField(child=serializers.DictField())
    cycle = serializers.BooleanField(required=False)

@extend_schema(
    tags=["animals", "animals_new"],
    description="API do zarządzania zwierzętami, ich cechami, galeriami oraz relacjami rodzic–dziecko."
)
class AnimalViewSet(viewsets.ModelViewSet):
    """
    list, retrieve, create, update, partial_update, destroy dla modelu Animal
Opis filtrów

organization-type

Odczytuje parametr query organization-type (np. ?organization-type=ngo,private) i dzieli go po przecinkach.
Filtruje zwierzęta powiązane przez właściciela -> membership -> organization, porównując pole type organizacji (owner__memberships__organization__type__in=org_list).
organization-id

Parametr organization-id (np. ?organization-id=1,2) rozdzielany po przecinkach.
Filtruje po identyfikatorze organizacji (owner__memberships__organization__id__in=org_ids).
gender

?gender=male,female — multi-value, dzieli i używa gender__in=gender_list.
species

?species=dog,cat — multi-value, filtr species__in=species_list.
breed

?breed=husky,labrador — multi-value, filtr breed__in=breed_list.
location

?location=tokyo,warsaw — traktuje każdy element jako wartość pola location i robi location__in=locations. Uwaga: działa poprawnie tylko jeśli typ pola location jest zgodny z wartościami (stringy vs geometrias).
name

?name=rex — search case-insensitive przez name__icontains=search_param.
range (zasieg) — geodjango

?range=5000 (wartość w metrach) konwertowana do float. Pobierany jest user.location. Jeżeli istnieje, wykonywane jest:
wykluczenie wpisów bez lokalizacji (exclude(location__isnull=True)),
filtr odległości location__distance_lte=(user_location, D(m=max_distance)),
annotate distance annotate(distance=Distance("location", user_location)),
sortowanie po odległości order_by("distance").

###################################################################################

Przykład użycia (filtrowanie po lokalizacji i zasięgu):
http://localhost/animals/animals/?location=SRID=4326;POINT (17 51)&range=1000000


Wymaga importów i konfiguracji GeoDjango: from django.contrib.gis.measure import D i from django.contrib.gis.db.models.functions import Distance.


filtrowanie po zakresie wieku (np. ?age_min=2&age_max=5 lub ?age-range=2-5 lub ?age_range=2,5)

localhost/animals/animals/?age-range=2-3
localhost/animals/animals/?age-min=2&age-max=3


filtrowanie po cechach (np. ?characteristics=friendly,vaccinated)

?characteristics=sterylizacja/kastracj, przyjazny, zaszczepiony


filtrowanie po miastach (np. ?city=Warszawa,Kraków)
?city=Warszawa,Kraków

filtrowanie po wielkości (np. ?size=SMALL,MEDIUM)
localhost/animals/animals/?size=MEDIUM
    """
    queryset = Animal.objects.all()
    serializer_class = AnimalSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    # Disable pagination so list endpoints return plain arrays.
    #pagination_class = None
    # DEFAULT_LIMIT = 10
    # MAX_LIMIT = 50

    # def list(self, request, *args, **kwargs):
    #     """Return a plain list of serialized animals without pagination."""
    #     queryset = self.filter_queryset(self.get_queryset())
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)

    def perform_create(self, serializer):
        # automatycznie ustawia właściciela na zalogowanego użytkownika
        # jeśli zwierzę jest przypisane do organizacji, ustaw ownera na właściciela organizacji
        # i przypisz lokalizację organizacji, jeśli jest dostępna
        organization = serializer.validated_data.get("organization")
        location = serializer.validated_data.get("location")
        save_kwargs = {}
        if organization:
            owner = organization.user
            save_kwargs["owner"] = owner
            if location is None:
                address = getattr(organization, "address", None)
                organization_location = getattr(address, "location", None)
                location = organization_location or getattr(owner, "location", None)
            if location is not None:
                save_kwargs["location"] = location
            serializer.save(**save_kwargs)
            return
        owner = self.request.user if self.request.user.is_authenticated else None
        if owner:
            save_kwargs["owner"] = owner
            if location is None:
                owner_location = getattr(owner, "location", None)
                if owner_location is not None:
                    save_kwargs["location"] = owner_location
            serializer.save(**save_kwargs)
            return
        serializer.save()

    def get_queryset(self):
        qs = Animal.objects.all().order_by('-created_at')
        params = self.request.query_params
        user_location = (
            getattr(self.request.user, "location", None)
            if self.request.user and self.request.user.is_authenticated
            else None
        )
        user_location = (
            getattr(self.request.user, "location", None)
            if self.request.user and self.request.user.is_authenticated
            else None
        )





        liked_by_param = params.get('liked_by') or params.get('liked-by')
        liked_only_param = params.get('liked')
        liked_user_id = None

        # If requester is not authenticated, do not show any liked animals
        if (liked_by_param or liked_only_param) and not (self.request.user and self.request.user.is_authenticated):
            return Animal.objects.none()

        if liked_by_param:
            try:
                liked_user_id = int(liked_by_param)
            except (TypeError, ValueError):
                liked_user_id = None
        elif liked_only_param and str(liked_only_param).lower() in ("1", "true", "yes"):
            liked_user_id = self.request.user.id

        if liked_user_id:
            animal_content_type = ContentType.objects.get_for_model(Animal)
            liked_animal_ids = (
                Reaction.objects.filter(
                    user_id=liked_user_id,
                    reaction_type=ReactionType.LIKE,
                    reactable_type=animal_content_type,
                )
                .values_list("reactable_id", flat=True)
            )
            qs = qs.filter(id__in=liked_animal_ids)

       



        # multi-value filtering for organization types
        org_param = params.get('organization-type')
        if org_param:
            org_list = [t.strip() for t in org_param.split(',') if t.strip()]
            qs = qs.filter(owner__memberships__organization__type__in=org_list)

        # filtrowanie zwierząt należących do podanych organizacji
        org_id_param = params.get('organization-id')
        if org_id_param:
            org_ids = [oid.strip() for oid in org_id_param.split(',') if oid.strip()]
            qs = qs.filter(owner__memberships__organization__id__in=org_ids)

        org_id_param2 = params.get('organization-ids')
        if org_id_param2:
            org_ids = [oid.strip() for oid in org_id_param2.split(',') if oid.strip()]
            qs = qs.filter(organization__id__in=org_ids)

        

       

        # # limit pagination
        # try:
        #     limit = int(params.get('limit', self.DEFAULT_LIMIT))
        # except (TypeError, ValueError):
        #     limit = self.DEFAULT_LIMIT
        # limit = max(1, min(limit, self.MAX_LIMIT))


        #user_location = getattr(self.request.user, "location", None)

        # filtrowanie po płci (parametr gender: wartości wielokrotne rozdzielone przecinkami)
        gender_param = params.get('gender')
        if gender_param:
            gender_list = [g.strip() for g in gender_param.split(',') if g.strip()]
            qs = qs.filter(gender__in=gender_list)
        
        # multi-value filtering for species (e.g. ?species=dog,cat)
        species_param = params.get('species')
        if species_param:
            species_list = [s.strip() for s in species_param.split(',') if s.strip()]
            qs = qs.filter(species__in=species_list)

        breed_param = params.get('breed')
        if breed_param:
            breed_list = [b.strip() for b in breed_param.split(',') if b.strip()]
            qs = qs.filter(breed__in=breed_list)

        # multi-value filtering for location
        location_param = params.get('location')
        location_point = None
        if location_param:
            locations = [loc.strip() for loc in location_param.split(',') if loc.strip()]
            try:
                location_point = GEOSGeometry(locations[0])
            except (ValueError, GEOSException, IndexError):
                location_point = None
            if location_point and not params.get('range'):
                qs = qs.filter(location=location_point)


        # wyszukiwanie po nazwie (niewrażliwe na wielkość liter) — spacje w parametrach URL koduj jako %20 lub "+"
        # np. GET /animals/?name=Animal%201 lub /animals/?name=Animal+1
        search_param = params.get('name')
        if search_param:
            # support multiple comma-separated search terms, e.g. ?name=Animal 1,Animal 2
            terms = [t.strip() for t in search_param.split(',') if t.strip()]
            if terms:
                q = Q()
            for t in terms:
                q |= Q(name__icontains=t)
            qs = qs.filter(q)

        # filtrowanie po zasięgu (parametr "zasieg" – wartość w metrach)

        zasieg_param = params.get('range')
        reference_point = location_point or user_location
        if reference_point:
            qs = qs.exclude(location__isnull=True).annotate(
                distance=Distance("location", reference_point)
            )

            if zasieg_param:
                try:
                    max_distance = float(zasieg_param)
                    qs = qs.filter(
                        location__distance_lte=(reference_point, D(m=max_distance))
                    )
                except (TypeError, ValueError):
                    pass

            qs = qs.order_by("distance")
        elif zasieg_param:
            # brak punktu odniesienia – ignorujemy filtr zasięgu
            try:
                float(zasieg_param)
            except (TypeError, ValueError):
                pass

        age_param = params.get('age')
        if age_param:
            try:
                age = int(age_param)

                today = date.today()
                # Animals whose birth_date makes them exactly `age` years old
                max_birth = today - relativedelta(years=age)
                min_birth = today - relativedelta(years=age + 1)

                qs = qs.filter(
                    birth_date__gt=min_birth,
                    birth_date__lte=max_birth
                )
            except (TypeError, ValueError):
                pass

        # filtrowanie po zakresie wieku (np. ?age_min=2&age_max=5 lub ?age-range=2-5 lub ?age_range=2,5)
        age_min_param = params.get('age_min') or params.get('age-min')
        age_max_param = params.get('age_max') or params.get('age-max')
        age_range_param = params.get('age_range') or params.get('age-range')

        if age_range_param and not (age_min_param or age_max_param):
            # wspiera formaty "2-5", "2,5", "2:5"
            sep = '-' if '-' in age_range_param else (',' if ',' in age_range_param else (':' if ':' in age_range_param else None))
            if sep:
                parts = [p.strip() for p in age_range_param.split(sep) if p.strip()]
                if len(parts) == 2:
                    age_min_param, age_max_param = parts[0], parts[1]

        try:
            today = date.today()
            if age_min_param and age_max_param:
                min_age = int(age_min_param)
                max_age = int(age_max_param)
                if min_age > max_age:
                    min_age, max_age = max_age, min_age
                # dla zakresu [min_age, max_age] przyjmujemy:
                # birth_date > today - (max_age+1) lat i birth_date <= today - min_age lat
                lower_birth = today - relativedelta(years=(max_age + 1))
                upper_birth = today - relativedelta(years=min_age)
                qs = qs.filter(birth_date__gt=lower_birth, birth_date__lte=upper_birth)
            elif age_min_param:
                min_age = int(age_min_param)
                # wiek >= min_age  => birth_date <= today - min_age lat
                upper_birth = today - relativedelta(years=min_age)
                qs = qs.filter(birth_date__lte=upper_birth)
            elif age_max_param:
                max_age = int(age_max_param)
                # wiek <= max_age => birth_date > today - (max_age+1) lat
                lower_birth = today - relativedelta(years=(max_age + 1))
                qs = qs.filter(birth_date__gt=lower_birth)
        except (TypeError, ValueError):
            # nieprawidłowe wartości wieku — ignoruj filtr
            pass


    
        # multi-value filtering for characteristics (JSONField `characteristic_board` stores a list of objects)
        char_param = params.get('characteristics')
        if char_param:
            try:
                parsed = json.loads(char_param)
                # support passing a JSON array of objects like:
                # [{"bool": false, "title": "akceptuje koty"}, {"bool": true, "title": "sterylizacja/kastracj"}]
                if isinstance(parsed, list) and all(isinstance(i, dict) for i in parsed):
                    # keep only titles that are true
                    char_list = [i.get('title') for i in parsed if (i.get('bool') is True or i.get('value') is True) and i.get('title')]
                else:
                    raise ValueError("not a list of dicts")
            except (ValueError, TypeError, json.JSONDecodeError):
            # fallback: accept comma-separated titles e.g. ?characteristics=tail,vaccinated
                char_list = [c.strip() for c in char_param.split(',') if c.strip()]

            # require each requested characteristic title to be present with a true value
            for c in char_list:
                qs = qs.filter(
                    Q(characteristic_board__contains=[{"title": c, "bool": True}]) |
                    Q(characteristic_board__contains=[{"title": c, "value": True}])
                )

        city_param = params.get('city')
        if city_param:
            city_str = city_param.strip()
            if city_str:
                qs = qs.filter(city__icontains=city_str)

        # sortowanie po wielkości (parametr size: "asc" lub "desc")
        size_param = params.get('size')
        if size_param:
            size_param = [loc.strip() for loc in size_param.split(',') if loc.strip()]
            qs = qs.filter(size__in=size_param)


        

        user_animals_param = params.get('user-animals') or params.get('user_animals')
        if user_animals_param and self.request.user and self.request.user.is_authenticated:
            if str(user_animals_param).lower() in ("1", "true", "yes"):
                qs = qs.filter(owner=self.request.user)        




        return qs
        # if user_location is None:
        #     return super().get_queryset().all()
        # # sortuje zwierzęta według odległości od użytkownika
        # return super().get_queryset() \
        #     .annotate(distance=Distance("location", user_location)) \
        #     .order_by("distance")
    

    
    
    

@extend_schema(
    tags=["animals_new_home"],
)
class AnimalRecentlyAddedViewSet(viewsets.ReadOnlyModelViewSet):
    """
    AnimalRecentlyAddedViewSet
    ==========================

    Endpoint tylko do odczytu zwracający **najnowsze** zwierzęta,
    domyślnie posortowane malejąco po `created_at` (ostatnio dodane najpierw).

    Parametry zapytania
    -------------------
    - **limit** (int, opcjonalny)  
      Maksymalna liczba wyników (1–50, domyślnie 10).

    - **species** (str, opcjonalny)  
      Jeden lub więcej gatunków oddzielonych przecinkami, np. `dog,cat`.

    - **organization-type** (str, opcjonalny)  
      Typy organizacji właściciela (wartości rozdzielone przecinkami):  
        • `SHELTER` – Schronisko / Fundacja  
        • `BREEDER` – Hodowla  
        • `CLINIC`  – Gabinet weterynaryjny  
        • `SHOP`    – Sklep zoologiczny  
        • `OTHER`   – Inne

    - **name** (str, opcjonalny)  
      Fragment nazwy zwierzęcia (niewrażliwy na wielkość liter).

    - **characteristics** (str, opcjonalny)  
      Lista kluczy cech boolowskich (przecinkami).  
      Zwracane są tylko zwierzęta, dla których każda wymieniona cecha ma
      wartość `True`, np. `characteristics=friendly,vaccinated`.

    Sortowanie i wyszukiwanie
    -------------------------
    - Wspiera standardowe parametry DRF `ordering` (pola `created_at`, `id`)  
      oraz `search` w polach `name`, `description`.

    Przykład
    --------
    ```http
    GET /animals/latest/?limit=20
        &species=dog,cat
        &organization-type=SHELTER
        &characteristics=friendly,vaccinated
    ```
    Zwraca maks. 20 najnowszych psów lub kotów należących do schronisk,
    które są przyjazne i zaszczepione.
    """
    
    
    serializer_class = RecentlyAddedAnimalSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'id']

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 50

    def get_queryset(self):
        qs = Animal.objects.all().order_by('-created_at')
        params = self.request.query_params

        # multi-value filtering for species (e.g. ?species=dog,cat)
        species_param = params.get('species')
        if species_param:
            species_list = [s.strip() for s in species_param.split(',') if s.strip()]
            qs = qs.filter(species__in=species_list)

        breed_param = params.get('breed')
        if breed_param:
            breed_list = [b.strip() for b in breed_param.split(',') if b.strip()]
            qs = qs.filter(breed__in=breed_list)

        # multi-value filtering for organization types
        org_param = params.get('organization-type')
        if org_param:
            org_list = [t.strip() for t in org_param.split(',') if t.strip()]
            qs = qs.filter(owner__memberships__organization__type__in=org_list)

        # search by name (case-insensitive)
        search_param = params.get('name')
        if search_param:
            qs = qs.filter(name__icontains=search_param)

        # limit pagination
        try:
            limit = int(params.get('limit', self.DEFAULT_LIMIT))
        except (TypeError, ValueError):
            limit = self.DEFAULT_LIMIT
        limit = max(1, min(limit, self.MAX_LIMIT))

        # multi-value filtering for characteristics (e.g. ?characteristics=tail,vaccinated)
        char_param = params.get('characteristics')
        if char_param:
            char_list = [c.strip() for c in char_param.split(',') if c.strip()]
            # multi-value filtering for characteristics (e.g. ?characteristics=tail,vaccinated)
            char_param = params.get('characteristics')
            if char_param:
                char_list = [c.strip() for c in char_param.split(',') if c.strip()]
                qs = qs.filter(
                    characteristics_values__characteristics__characteristic__in=char_list,
                    characteristics_values__value=True
                ).distinct()

        return qs[:limit]
    


@extend_schema(
    tags=["animals_filtering", "animals_filtering_advanced", "organizations_aniamls_filtering"],
)
class AnimalFilterViewSet(viewsets.ReadOnlyModelViewSet):
    
    """
    AnimalFilterViewSet
    ===================

    Endpoint tylko do odczytu umożliwiający filtrowanie listy zwierząt
    według wielu kryteriów: gatunku, danych o organizacji właściciela,
    cech fizycznych, lokalizacji i innych.

    Parametry zapytania
    -------------------
    - **limit** (int, opcjonalny)  
      Maksymalna liczba wyników na stronę (1–50, domyślnie 10 – zgodnie z paginacją).

    - **species** (str, opcjonalny)  
      Jeden lub więcej gatunków rozdzielonych przecinkami, np. `dog,cat`.

    - **organization-type** (str, opcjonalny)  
      Typy organizacji właściciela, rozdzielone przecinkami:  
        • `SHELTER` – Schronisko / Fundacja  
        • `BREEDER` – Hodowla  
        • `CLINIC`  – Gabinet weterynaryjny  
        • `SHOP`    – Sklep zoologiczny  
        • `OTHER`   – Inne

    - **organization-id** (int, opcjonalny)  
      Jeden lub więcej identyfikatorów organizacji (przecinkami) – zwraca
      wyłącznie zwierzęta należące do tych organizacji.

    - **name** (str, opcjonalny)  
      Niewrażliwe na wielkość liter wyszukiwanie fragmentu nazwy zwierzęcia.

    - **size** (str, opcjonalny)  
      Jeden lub więcej rozmiarów: `SMALL`, `MEDIUM`, `LARGE` (przecinkami).

    - **gender** (str, opcjonalny)  
      Jedna lub więcej płci: `MALE`, `FEMALE`, `OTHER` (przecinkami).

    - **age** (int, opcjonalny)  
      Dokładny wiek w pełnych latach (wyliczany z pola `birth_date`).

    - **characteristics** (str, opcjonalny)  
      Lista kluczy cech **boolowskich** (przecinkami); zwracane są tylko
      zwierzęta, dla których każda z wymienionych cech ma wartość `True`.  
      Przykład: `characteristics=friendly,vaccinated`.

    - **location** (str, opcjonalny)  
      Lista kodów lokalizacji obsługiwanych przez `LocationField`
      (np. ID miasta, kody pocztowe) rozdzielonych przecinkami.

    - **range** (float, opcjonalny)  
      Maksymalna odległość w **metrach** od lokalizacji użytkownika.
      Wymaga ustawionego pola `location`; łączy się z innymi filtrami i
      sortuje wyniki według odległości.

    - **breed-groups** (str, opcjonalny)  
      Jedna lub więcej nazw grup rasowych, rozdzielonych przecinkami,
      np. `toy,herding`.

    Sortowanie i wyszukiwanie
    -------------------------
    - Obsługuje standardowy mechanizm DRF `ordering` (po `created_at`, `id`;
      domyślnie najnowsze pierwsze) oraz `search` po `name` i `description`.

    Przykład
    --------
    ```http
    GET /animals/filtering/?species=dog,cat
        &organization-type=SHELTER
        &characteristics=friendly,vaccinated
        &size=SMALL,MEDIUM
        &range=5000
    ```
    Zwraca przyjazne, zaszczepione psy lub koty znajdujące się w promieniu
    5 km od użytkownika, należące do schronisk lub fundacji, ograniczone do
    podanych rozmiarów.



    29250911
    Inny przykład (filtrowanie po grupach rasowych i rasie):

    http://localhost/animals/filtering/?breed=Mixed
    """


    serializer_class = RecentlyAddedAnimalSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'id']
    
    def get_queryset(self):
        qs = Animal.objects.all().order_by('-created_at')
        params = self.request.query_params

        # multi-value filtering for species (e.g. ?species=dog,cat)
        species_param = params.get('species')
        if species_param:
            species_list = [s.strip() for s in species_param.split(',') if s.strip()]
            qs = qs.filter(species__in=species_list)

        # multi-value filtering for organization types
        org_param = params.get('organization-type')
        if org_param:
            org_list = [t.strip() for t in org_param.split(',') if t.strip()]
            qs = qs.filter(owner__memberships__organization__type__in=org_list)

        # search by name
        search_param = params.get('name')
        if search_param:
            qs = qs.filter(name__icontains=search_param)

        # multi-value filtering for characteristics
        char_param = params.get('characteristics')
        if char_param:
            char_list = [c.strip() for c in char_param.split(',') if c.strip()]
            qs = qs.filter(
                characteristics_values__characteristic__in=char_list,
                characteristics_values__value=True
            ).distinct()

        # multi-value filtering for location
        location_param = params.get('location')
        if location_param:
            locations = [loc.strip() for loc in location_param.split(',') if loc.strip()]
            qs = qs.filter(location__in=locations)

        # support Polish “gatunek” query parameter for species filtering
        gatunek_param = params.get('species')
        if gatunek_param:
            gatunek_list = [g.strip() for g in gatunek_param.split(',') if g.strip()]
            qs = qs.filter(species__in=gatunek_list)

        age_param = params.get('age')
        if age_param:
            try:
                age = int(age_param)

                today = date.today()
                # Animals whose birth_date makes them exactly `age` years old
                max_birth = today - relativedelta(years=age)
                min_birth = today - relativedelta(years=age + 1)

                qs = qs.filter(
                    birth_date__gt=min_birth,
                    birth_date__lte=max_birth
                )
            except (TypeError, ValueError):
                pass


        # multi-value filtering for breed groups (e.g. ?breed-groups=herding,toy)
        breed_groups_param = params.get('breed-groups')
        if breed_groups_param:
            group_list = [g.strip() for g in breed_groups_param.split(',') if g.strip()]
            qs = qs.filter(animal_breed_groups__group_name__in=group_list)

        breed_param = params.get('breed')
        if breed_param:
            breed_list = [b.strip() for b in breed_param.split(',') if b.strip()]
            qs = qs.filter(breed__in=breed_list)

        
        # sortowanie po wielkości (parametr size: "asc" lub "desc")
        size_param = params.get('size')
        if size_param:
            size_param = [loc.strip() for loc in size_param.split(',') if loc.strip()]
            qs = qs.filter(size__in=size_param)

        

        # filtrowanie po płci (parametr gender: wartości wielokrotne rozdzielone przecinkami)
        gender_param = params.get('gender')
        if gender_param:
            gender_list = [g.strip() for g in gender_param.split(',') if g.strip()]
            qs = qs.filter(gender__in=gender_list)

        # filtering by range (zasięg) – expects an integer value in query param “zasieg”


        # filtrowanie zwierząt należących do podanych organizacji
        org_id_param = params.get('organization-id')
        if org_id_param:
            org_ids = [oid.strip() for oid in org_id_param.split(',') if oid.strip()]
            qs = qs.filter(owner__memberships__organization__id__in=org_ids).distinct()

        org_id_param2 = params.get('organization-ids')
        if org_id_param2:
            org_ids = [oid.strip() for oid in org_id_param2.split(',') if oid.strip()]
            qs = qs.filter(organization__id__in=org_ids)

        
            
        # filtrowanie po zasięgu (parametr "zasieg" – wartość w metrach)
        zasieg_param = params.get('range')
        if user_location:
            qs = qs.exclude(location__isnull=True).annotate(
                distance=Distance("location", user_location)
            )

            if zasieg_param:
                try:
                    max_distance = float(zasieg_param)
                    qs = qs.filter(
                        location__distance_lte=(user_location, D(m=max_distance))
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

        

        
        return qs


            
        

       
        
    
        



    
    

@extend_schema(
    tags=["animal_characteristics", "animals_characteristics_new"],
    description="API for managing animal characteristics (boolean features)."
)
class AnimalCharacteristicViewSet(viewsets.ModelViewSet):
    """
    CRUD for AnimalCharacteristic
    """
    queryset = AnimalCharacteristic.objects.all()
    serializer_class = AnimalCharacteristicSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


@extend_schema(
    tags=["characteristics_animals_values"],
)
class CharacteristicsViewSet(viewsets.ModelViewSet):
    """
    Read-only view for listing all animal characteristics.
    """
    queryset = Characteristics.objects.all()
    serializer_class = CharacteristicsSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        return super().get_queryset()





@extend_schema(
    tags=["animal_galleries"],
    description="API for managing animal galleries (image URLs)."
)
class AnimalGalleryViewSet(viewsets.ModelViewSet):
    """
    CRUD for AnimalGallery
    """
    queryset = AnimalGallery.objects.all()
    serializer_class = AnimalGallerySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

@extend_schema(
    tags=["animal_parentages"],
    description="API for managing parent-child relationships between animals."
)
class AnimalParentViewSet(viewsets.ModelViewSet):
    """
    CRUD for AnimalParent (parent–child relationships)

    OPTIONS /animals/parent/  ->  list of available HTTP methods

    actions -> POST -> relation -> choices
    """
    queryset = AnimalParent.objects.all()
    serializer_class = AnimalParentSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    #http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]




@extend_schema(
    tags=["animal_family_tree"],
    description="API for retrieving the family tree of an animal (ancestors and descendants)."
)
class AnimalFamilyTreeViewSet(viewsets.ViewSet):
    """
    Read-only view for retrieving a simple family tree of an animal.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = FamilyTreeNodeSerializer

    def retrieve(self, request, pk=None):
        # get the target animal
        root = get_object_or_404(Animal, pk=pk)

        def build_node(animal, visited):
            node = {
                "id": animal.id,
                "name": animal.name,
                "image": animal.image.url if animal.image else None,
                
                "parents": [],
                "children": [],
            }
            # detect cycles
            if animal.id in visited:
                node["cycle"] = True
                return node

            visited.add(animal.id)

            # build parent subtree
            parent_rels = AnimalParent.objects.filter(animal=animal).select_related("parent")
            for rel in parent_rels:
                node["parents"].append(build_node(rel.parent, set(visited)))

            # build children subtree
            child_rels = AnimalParent.objects.filter(parent=animal).select_related("animal")
            for rel in child_rels:
                node["children"].append(build_node(rel.animal, set(visited)))

            return node

        tree = build_node(root, set())
        return Response(tree)
    



    

@extend_schema(
    tags=["animals_breed_groups", "animals_breed_groups_miots"],
    description="CRUD for AnimalsBreedGroups"
)
class AnimalsBreedGroupsViewSet(viewsets.ModelViewSet):
    """
    CRUD for AnimalsBreedGroups
    """
    queryset = AnimalsBreedGroups.objects.all()
    serializer_class = AnimalsBreedGroupsSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    
