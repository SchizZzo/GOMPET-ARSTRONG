from rest_framework import filters, viewsets
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly

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
    CharacteristicsSerializer,
    AnimalsBreedGroupsSerializer,


)
from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from datetime import date
from dateutil.relativedelta import relativedelta
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from django.db.models import Q
import json

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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'descriptions']
    ordering_fields = ['created_at', 'id']
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]
    MAX_LIMIT = 50

    def perform_create(self, serializer):
        # automatycznie ustawia właściciela na zalogowanego użytkownika
        serializer.save(owner=self.request.user)


    def get_queryset(self):
        qs = Animal.objects.all().order_by('-created_at')
        params = self.request.query_params

        def split(param_value):
            return [item.strip() for item in param_value.split(',') if item.strip()]

        org_param = params.get('organization-type')
        if org_param:
            org_list = split(org_param)
            if org_list:
                qs = qs.filter(owner__memberships__organization__type__in=org_list)

        org_id_param = params.get('organization-id')
        if org_id_param:
            org_ids = split(org_id_param)
            if org_ids:
                qs = qs.filter(owner__memberships__organization__id__in=org_ids)

        status_param = params.get('status')
        if status_param:
            statuses = split(status_param)
            if statuses:
                qs = qs.filter(status__in=statuses)

        life_period_param = params.get('life-period') or params.get('life_period')
        if life_period_param:
            life_periods = split(life_period_param)
            if life_periods:
                qs = qs.filter(life_period__in=life_periods)

        gender_param = params.get('gender')
        if gender_param:
            gender_list = split(gender_param)
            if gender_list:
                qs = qs.filter(gender__in=gender_list)

        species_param = params.get('species')
        if species_param:
            species_list = split(species_param)
            if species_list:
                qs = qs.filter(species__in=species_list)

        breed_param = params.get('breed')
        if breed_param:
            breed_list = split(breed_param)
            if breed_list:
                qs = qs.filter(breed__in=breed_list)

        size_param = params.get('size')
        if size_param:
            sizes = split(size_param)
            if sizes:
                qs = qs.filter(size__in=sizes)

        breed_groups_param = params.get('breed-groups')
        if breed_groups_param:
            group_list = split(breed_groups_param)
            if group_list:
                qs = qs.filter(animal_breed_groups__group_name__in=group_list)

        city_param = params.get('city')
        if city_param:
            cities = split(city_param)
            if cities:
                city_query = Q()
                for city in cities:
                    city_query |= Q(city__icontains=city)
                qs = qs.filter(city_query)

        location_point = None
        location_param = params.get('location')
        if location_param:
            locations = split(location_param)
            if locations:
                try:
                    location_point = GEOSGeometry(locations[0])
                except (ValueError, GEOSException):
                    location_point = None
                if location_point and not params.get('range'):
                    qs = qs.filter(location=location_point)

        search_param = params.get('name')
        if search_param:
            terms = split(search_param)
            if terms:
                query = Q()
                for term in terms:
                    query |= Q(name__icontains=term)
                qs = qs.filter(query)

        range_param = params.get('range')
        if range_param:
            try:
                max_distance = float(range_param)
            except (TypeError, ValueError):
                max_distance = None
            if max_distance is not None:
                point = location_point or getattr(self.request.user, 'location', None)
                if point:
                    qs = (
                        qs.exclude(location__isnull=True)
                        .filter(location__distance_lte=(point, D(m=max_distance)))
                        .annotate(distance=Distance('location', point))
                        .order_by('distance')
                    )

        age_param = params.get('age')
        if age_param:
            try:
                age = int(age_param)
            except (TypeError, ValueError):
                age = None
            if age is not None:
                today = date.today()
                max_birth = today - relativedelta(years=age)
                min_birth = today - relativedelta(years=age + 1)
                qs = qs.filter(birth_date__gt=min_birth, birth_date__lte=max_birth)

        age_min_param = params.get('age_min') or params.get('age-min')
        age_max_param = params.get('age_max') or params.get('age-max')
        age_range_param = params.get('age_range') or params.get('age-range')
        if age_range_param and not (age_min_param or age_max_param):
            for sep in ('-', ',', ':'):
                if sep in age_range_param:
                    parts = split(age_range_param.replace(sep, ','))
                    if len(parts) == 2:
                        age_min_param, age_max_param = parts
                    break

        try:
            today = date.today()
            if age_min_param and age_max_param:
                min_age = int(age_min_param)
                max_age = int(age_max_param)
                if min_age > max_age:
                    min_age, max_age = max_age, min_age
                lower_birth = today - relativedelta(years=(max_age + 1))
                upper_birth = today - relativedelta(years=min_age)
                qs = qs.filter(birth_date__gt=lower_birth, birth_date__lte=upper_birth)
            elif age_min_param:
                min_age = int(age_min_param)
                upper_birth = today - relativedelta(years=min_age)
                qs = qs.filter(birth_date__lte=upper_birth)
            elif age_max_param:
                max_age = int(age_max_param)
                lower_birth = today - relativedelta(years=(max_age + 1))
                qs = qs.filter(birth_date__gt=lower_birth)
        except (TypeError, ValueError):
            pass

        char_param = params.get('characteristics')
        if char_param:
            titles = []
            try:
                parsed = json.loads(char_param)
            except (TypeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        if (item.get('bool') is True or item.get('value') is True) and item.get('title'):
                            titles.append(item['title'])
            if not titles:
                titles = split(char_param)
            for title in titles:
                qs = qs.filter(
                    Q(characteristic_board__contains=[{"title": title, "bool": True}])
                    | Q(characteristic_board__contains=[{"title": title, "value": True}])
                )
            if titles:
                qs = qs.filter(
                    characteristics_values__characteristics__characteristic__in=titles,
                    characteristics_values__value=True,
                )

        return qs.distinct()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limit_param = request.query_params.get('limit')
        limit = None
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except (TypeError, ValueError):
                limit = None
            else:
                limit = max(1, min(limit, self.MAX_LIMIT))
        if limit is not None:
            queryset = queryset[:limit]

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
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

    