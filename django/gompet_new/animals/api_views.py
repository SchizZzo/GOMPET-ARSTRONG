from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
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


Przykład użycia (filtrowanie po lokalizacji i zasięgu):
http://localhost/animals/animals/?location=SRID=4326;POINT (17 51)&range=1000000


Wymaga importów i konfiguracji GeoDjango: from django.contrib.gis.measure import D i from django.contrib.gis.db.models.functions import Distance.

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
        serializer.save(owner=self.request.user)

    def get_queryset(self):
        qs = Animal.objects.all().order_by('-created_at')
        params = self.request.query_params



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
        if zasieg_param:
            try:
                if location_point is None:
                    user_location = getattr(self.request.user, "location", None)
                max_distance = float(zasieg_param)
                point = location_point or user_location
                if point:
                    qs = (
                        qs.exclude(location__isnull=True)
                        .filter(location__distance_lte=(point, D(m=max_distance)))
                        .annotate(distance=Distance("location", point))
                        .order_by("distance")
                    )
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
            qs = qs.filter(owner__memberships__organization__id__in=org_ids)
            
        # filtrowanie po zasięgu (parametr "zasieg" – wartość w metrach)
        zasieg_param = params.get('range')
        if zasieg_param:
            try:
                max_distance = float(zasieg_param)
                user_location = getattr(self.request.user, "location", None)
                print(f"User location: {user_location}, Max distance: {max_distance}")
                if user_location:
                    qs = (
                    qs.exclude(location__isnull=True)
                    .filter(location__distance_lte=(user_location, D(m=max_distance)))
                    .annotate(distance=Distance("location", user_location))
                    .order_by("distance")
                    )
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

    