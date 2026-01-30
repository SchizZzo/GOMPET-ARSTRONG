# GOMPET_2


make all - aby uruchmic wszystko co potrzebnne przy pierwszym uruchomieniu.

all:
	$(MAKE) makemigrations
	$(MAKE) migrate
	$(MAKE) collectstatic
	$(MAKE) populatedb
	$(MAKE) createsuperuser
	$(MAKE) run

po uruchomieniu wszyskiekgo bedzie wstepnie wypelniona baza jesli utworzyc superuser to bedziesz miec uzytkownika do testow.


dokładny adres dla api:
http://localhost/api/v2/redoc/

np. bierzesz adres 
http://localhost/api/v2/users/users/

to musisz z endpointa usunac /api/v2 aby działalo poprawnie.

POST
http://localhost/users/users/

## Backend API

Dokumentacja interaktywna: `http://localhost/api/v2/redoc/` oraz `http://localhost/api/v2/docs/`.

### Endpointy (główne) i filtry

> Uwaga: endpointy w aplikacji działają **bez** prefiksu `/api/v2` (prefiks dotyczy tylko dokumentacji).

**Animals**
- `/animals/animals/` — CRUD zwierząt; filtry: `organization-type`, `organization-id`, `gender`, `species`, `breed`, `name`, `location`, `range`, `age`, `age-min`, `age-max`, `age-range`, `characteristics`, `city`, `size`.  
  Przykład: `GET /animals/animals/?location=SRID=4326;POINT (17 51)&range=1000000`
- `/animals/latest/` — ostatnio dodane; filtry: `limit`, `species`, `breed`, `organization-type`, `name`, `characteristics`, + `ordering`, `search`.
- `/animals/filtering/` — rozbudowane filtrowanie; filtry: `limit`, `species`, `organization-type`, `organization-id`, `name`, `size`, `gender`, `age`, `characteristics`, `location`, `range`, `breed`, `breed-groups`, + `ordering`, `search`.
- `/animals/animal-breed/`, `/animals/characteristics/`, `/animals/characteristics-values/`, `/animals/galleries/`, `/animals/parents/`, `/animals/family-tree/` — zasoby pomocnicze (rasy, cechy, galeria, relacje rodzinne).

**Users / Organizations**
- `/users/users/` — użytkownicy (CRUD).
- `/users/organizations/` — organizacje; filtry: `organization-type`, `species`, `breeding-type`, `user-id`.
- `/users/organization-latest/` — najnowsze organizacje; filtry: `organization-type`, `limit`.
- `/users/organization-filtering/` — filtrowanie organizacji; filtry: `name`, `organization-type`, `range`, `breeding-type`, `species`, `city`.
- `/users/organization-members/` — członkowie organizacji; filtry: `mine`, `organization-id`, `organization-id-confirmed`, `organization-member-user-id`.
- `/users/organization-addresses/` — adresy organizacji; filtry: `city`, `organization-type`.
- `/users/species/` — gatunki (read-only).
- `/users/organization-types/` — lista typów organizacji.
- `/users/organization-member-roles/` — lista ról członków organizacji.

**Articles / Posts / Litters / Common**
- `/articles/articles/` — artykuły; filtry: `search`, `ordering`, `categories`, `categories__slug`, `category`, `category-slug`, `has-category`.
- `/articles/articles-latest/` — najnowsze artykuły; filtry: `author`, `categories`, `categories__slug`, `limit`, + `search`, `ordering`.
- `/articles/article-categories/` — kategorie artykułów; filtry: `search`, `ordering`.
- `/posts/posts/` — posty (CRUD).
- `/litters/litters/`, `/litters/litter-animals/` — mioty i przypisania.
- `/common/comments/`, `/common/reactions/`, `/common/content-types/`, `/common/notifications/` — komentarze, reakcje, typy treści, powiadomienia.

### Przykłady request/response

**Filtracja zwierząt w promieniu 5 km**
```http
GET /animals/filtering/?species=dog,cat&range=5000&organization-type=SHELTER
```
```json
[
  {
    "id": 42,
    "name": "Luna",
    "species": "dog",
    "breed": "mixed",
    "gender": "FEMALE",
    "size": "MEDIUM",
    "city": "Warszawa",
    "distance": 3120,
    "organization": {
      "id": 5,
      "type": "SHELTER",
      "name": "Schronisko Północ"
    }
  }
]
```

**Najnowsze organizacje z filtrem typu**
```http
GET /users/organization-latest/?limit=10&organization-type=SHELTER,CLINIC
```
```json
[
  {
    "id": 5,
    "type": "SHELTER",
    "name": "Schronisko Północ",
    "created_at": "2024-09-01T10:15:00Z",
    "address": {
      "city": "Warszawa",
      "street": "Sezamkowa",
      "zip_code": "00-001"
    }
  }
]
```

**Artykuły z wyszukiwaniem i kategorią**
```http
GET /articles/articles/?search=adopcja&categories__slug=porady&ordering=-created_at
```
```json
[
  {
    "id": 7,
    "slug": "adopcja-krok-po-kroku",
    "title": "Adopcja krok po kroku",
    "created_at": "2024-08-10T08:00:00Z"
  }
]
```

### Uwierzytelnienie i role
- **Odczyt (GET/HEAD/OPTIONS)**: publiczny dla większości endpointów.  
- **Zapis (POST/PUT/PATCH/DELETE)**: wymaga logowania; uprawnienia są weryfikowane przez role członków organizacji (`OWNER`, `STAFF`, `VOLUNTEER`, `MODERATOR`, `PARTNER`, `FINANCE`, `CONTENT`, `VIEWER`).  
- Dla części zasobów (np. artykuły) obowiązuje standard `DjangoModelPermissionsOrAnonReadOnly` — odczyt publiczny, zapis tylko dla użytkowników z odpowiednimi uprawnieniami.

### Geolokalizacja i wpływ na wyniki
- System przechowuje pozycje w polach `location` (GeoDjango `PointField`) dla użytkownika, organizacji (`address.location`) oraz zwierząt.  
- Parametr `range` (w metrach) wykorzystuje lokalizację zalogowanego użytkownika:
  - jeśli lokalizacja jest ustawiona → wyniki są filtrowane po odległości i sortowane rosnąco po dystansie,  
  - jeśli brak lokalizacji → `range` jest ignorowany.  
- Dla zwierząt można dodatkowo podać `location=SRID=4326;POINT (lng lat)`, aby zawęzić wyniki do punktu odniesienia.

## SMTP2GO (reset haseł i e-maile)

Konfiguracja SMTP2GO jest oparta o zmienne środowiskowe w `django/gompet_new/gompet_new/settings.py`.
Wystarczy dodać poniższe zmienne do środowiska (np. `.env` używanego przez `docker-compose`):

```
SMTP2GO_HOST=mail.smtp2go.com
SMTP2GO_PORT=587
SMTP2GO_USERNAME=twoj_uzytkownik
SMTP2GO_PASSWORD=twoje_haslo
SMTP2GO_USE_TLS=true
SMTP2GO_USE_SSL=false
DEFAULT_FROM_EMAIL=no-reply@twoja-domena.pl
SERVER_EMAIL=no-reply@twoja-domena.pl
```

Uwagi:
- SMTP2GO obsługuje port `587` (TLS) i `465` (SSL); użyj tylko jednego z trybów.
- Jeżeli korzystasz z resetu hasła, upewnij się, że endpointy resetu w backendzie faktycznie wysyłają e-mail (logika resetu musi używać `send_mail`/`EmailMessage`).
