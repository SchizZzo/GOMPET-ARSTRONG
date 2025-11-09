# Dokumentacja kluczowych endpointów API

Niniejszy dokument opisuje podstawowe zasady korzystania z najważniejszych
publicznych endpointów REST API dostępnych w projekcie.  Wszystkie ścieżki są
podawane względem głównego prefiksu aplikacji (np. `/users/`, `/animals/`).

## Uwierzytelnianie

* Tokeny JWT (SimpleJWT) są wydawane pod `/users/auth/token/` oraz
  `/users/auth/token/refresh/`.
* Jeśli w opisie endpointu nie zaznaczono inaczej, odczyt danych (metody `GET`)
  jest publiczny, a modyfikacje (`POST`, `PUT`, `PATCH`, `DELETE`) wymagają
  aktywnego tokenu JWT.

---

## Moduł Users

### `/users/users/`

| Metoda | Opis | Uprawnienia |
| --- | --- | --- |
| `GET` | Lista użytkowników lub szczegóły (`/users/users/{id}/`). | Wymaga logowania |
| `POST` | Rejestracja nowego użytkownika. | Publiczny |
| `PUT/PATCH/DELETE` | Aktualizacja bądź usunięcie użytkownika. | Wymaga logowania |

**Ważne pola**

| Pole | Typ | Uwagi |
| --- | --- | --- |
| `email` | string | Wymagane przy tworzeniu. |
| `password` | string | Tylko do zapisu; przy aktualizacji opcjonalne. |
| `first_name`, `last_name` | string | Opcjonalne, ale rekomendowane. |
| `image` | base64 | Obsługuje zwykłe base64 lub `data:image/...` URI. |
| `phone`, `role` | string | Pola opcjonalne. |

Serwer zwraca również pola tylko do odczytu, m.in. `full_name`, `created_at`,
`updated_at` i flagi statusu konta.【F:django/gompet_new/users/api_views.py†L38-L75】【F:django/gompet_new/users/serializers.py†L24-L92】

---

### `/users/organizations/`

Endpoint CRUD zarządzający organizacjami, automatycznie przypisuje autora oraz
zakłada członkostwo właściciela podczas tworzenia rekordu.【F:django/gompet_new/users/api_views.py†L77-L170】

**Metody**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE` (tylko zalogowani).

**Kluczowe pola w żądaniu**

| Pole | Typ | Uwagi |
| --- | --- | --- |
| `type` | enum | Typ organizacji. |
| `name`, `email`, `phone`, `description` | string | `name` i `email` wymagane. |
| `image` | base64 | Opcjonalne logo. |
| `address` | obiekt | Wymaga pól `street`, `house_number`, `city`, `zip_code`, `lat`, `lng`, `location` (GeoJSON `Point`). |

**Filtry zapytań (`GET /users/organizations/`)**

| Parametr | Opis |
| --- | --- |
| `name` | Fragment nazwy (wyszukiwanie `icontains`). |
| `city` | Dokładne dopasowanie miasta (case-insensitive). |
| `organization-type` | Lista typów (oddzielone przecinkami). |
| `species` | Lista gatunków obsługiwanych przez organizację. |
| `breeding-type` | Lista obsługiwanych typów hodowli. |
| `range` | Promień w metrach od lokalizacji użytkownika (wymaga `user.location`). |
| `limit` | Maksymalna liczba wyników (opcjonalne). |

---

### `/users/species/`

Read-only API do zarządzania gatunkami zwierząt. Udostępnia `GET /users/species/`
i `GET /users/species/{id}/`. W odpowiedziach znajdują się pola `id`, `name` oraz
`description`. Modyfikacje nie są dostępne.【F:django/gompet_new/users/api_views.py†L196-L210】【F:django/gompet_new/users/serializers.py†L132-L149】

---

## Moduł Animals

### `/animals/animals/`

Pełny CRUD dla modelu `Animal`. Tworzenie ustawia właściciela na aktualnie
zalogowanego użytkownika, a pole `gallery` umożliwia przesłanie wielu zdjęć w
formacie base64.【F:django/gompet_new/animals/api_views.py†L38-L215】【F:django/gompet_new/animals/serializers.py†L121-L230】

**Parametry filtrowania (`GET /animals/animals/`)**

| Parametr | Znaczenie |
| --- | --- |
| `organization-type` | Lista typów organizacji właściciela. |
| `organization-id` | Lista identyfikatorów organizacji. |
| `status` | Lista statusów (`AVAILABLE`, `ADOPTED`, itp.). |
| `life-period` / `life_period` | Lista wartości cyklu życia. |
| `gender`, `species`, `breed`, `size` | Listy wartości rozdzielone przecinkami. |
| `breed-groups` | Nazwy grup rasowych (`AnimalsBreedGroups`). |
| `city` | Lista miast (dopasowanie `icontains`). |
| `name` | Frazy wyszukiwane po nazwie. |
| `location` | WKT/GeoJSON `Point`; bez `range` wymaga dokładnego dopasowania. |
| `range` | Promień w metrach od `location` lub od lokalizacji użytkownika. |
| `age` | Wiek w latach (dokładny). |
| `age-min` / `age_min`, `age-max` / `age_max` | Przedział wieku w latach. |
| `age-range` / `age_range` | Zakres wieku (`min-max`, `min,max`). |
| `characteristics` | Lista tytułów cech albo JSON z polami `title`/`bool`. |
| `limit` | Ograniczenie liczby wyników (maks. 50). |

**Kluczowe pola przy tworzeniu/aktualizacji**

| Pole | Typ | Uwagi |
| --- | --- | --- |
| `name`, `species`, `breed`, `gender`, `size` | wymagane pola opisowe. |
| `birth_date` | data | Na jej podstawie liczony jest wiek. |
| `descriptions`, `status`, `price`, `city`, `life_period` | pola opcjonalne. |
| `location` | GeoJSON/WKT `Point` | Pozwala na filtrowanie po odległości. |
| `gallery` | lista obiektów `{ "image": <base64> }` | Opcjonalna, ale każde zdjęcie musi zawierać klucz `image`. |
| `characteristicBoard` | lista obiektów z polami `title` oraz `bool`/`value`. |

Odpowiedź zawiera dodatkowe dane tylko do odczytu: `age`, `distance`, listy
`comments`, `reactions` oraz dane organizacji właściciela.【F:django/gompet_new/animals/serializers.py†L160-L229】

---

### `/animals/animal-breed/`

CRUD dla grup rasowych (`AnimalsBreedGroups`). Wymaga autoryzacji do zmian,
odczyt jest publiczny. Najważniejsze pola: `group_name`, `species`,
`description`, opcjonalnie zakresy wag i rozmiarów. Tworzenie i aktualizacja
akceptują standardowe pola modelu; odpowiedzi zawierają znaczniki czasu
`created_at` i `updated_at`.【F:django/gompet_new/animals/api_views.py†L404-L417】【F:django/gompet_new/animals/models.py†L322-L365】【F:django/gompet_new/animals/serializers.py†L360-L365】

---

### `/animals/parents/`

CRUD relacji rodzic–potomstwo (`AnimalParent`). Każdy rekord wymaga podania
`parent`, `animal` (oba ID zwierząt) oraz `relation` (np. `MOTHER`, `FATHER`,
`GUARDIAN`). Odpowiedź zwraca również `animal_id` potomka. Endpoint jest
przeznaczony do powiązań rodzinnych oraz budowania drzew genealogicznych.
`GET /animals/parents/{id}/` zwraca pojedynczą relację, a `GET /animals/family-tree/{id}/`
zwraca uproszczone drzewo całej rodziny.【F:django/gompet_new/animals/api_views.py†L309-L373】【F:django/gompet_new/animals/serializers.py†L55-L119】

---

## Moduł Common

### `/common/comments/`

Pełny CRUD na komentarzach. Tworząc komentarz należy wskazać powiązany obiekt
za pomocą pól `content_type` (ID lub zapis `app_label.model`) oraz `object_id`.
Dostępne są również pola opcjonalne, np. `rating`. W odpowiedzi otrzymasz dane
autora (`author`) oraz znaczniki czasu. Endpoint pozwala filtrować komentarze po
parametrach zapytania:

| Parametr | Opis |
| --- | --- |
| `content_type` | ID lub nazwa (`app_label.model`) typu obiektu. |
| `object_id` | ID obiektu powiązanego z komentarzem. |

Brak uprawnień do zapisu zwraca błąd 401.【F:django/gompet_new/common/api_views.py†L15-L78】【F:django/gompet_new/common/serializers.py†L18-L63】

---

### `/common/reactions/`

CRUD dla reakcji użytkowników (like/love/wow…). Wymagane pola przy tworzeniu to
`reaction_type`, `reactable_type` (ID lub `app_label.model`) oraz `reactable_id`
(obiekt docelowy). Dostępne typy reakcji: `LIKE`, `LOVE`, `WOW`, `SAD`,
`ANGRY`. Parametry zapytania `reactable_type` i `reactable_id` umożliwiają
filtrowanie listy reakcji. Dodatkowy endpoint
`GET /common/reactions/has-reaction/` zwraca ID reakcji zalogowanego użytkownika
(`reaction_id`) lub `0`, jeśli nie zareagował; wymaga parametrów
`reactable_type`, `reactable_id` oraz opcjonalnie `reaction_type` (domyślnie
`LIKE`).【F:django/gompet_new/common/api_views.py†L95-L190】【F:django/gompet_new/common/api_views.py†L205-L266】【F:django/gompet_new/common/models.py†L70-L111】

---

## Moduł Litters

### `/litters/litters/`

Endpoint tylko do odczytu prezentujący mioty (`Litter`). Obsługuje dwa parametry
zapytania (oba opcjonalne):

| Parametr | Opis |
| --- | --- |
| `organization-id` | ID organizacji; ma priorytet nad `user-id`. |
| `user-id` | ID właściciela miotu, używany gdy nie podano `organization-id`. |

Zwrotne dane zawierają podstawowe informacje o miocie (`title`, `description`,
`birth_date`, `status`, `species`, `breed`, `owner`, `organization`).
Endpoint `GET /litters/litter-animals/` pozwala zarządzać powiązaniami miot–zwierzę
(`LitterAnimalViewSet`).【F:django/gompet_new/litters/api_views.py†L1-L73】【F:django/gompet_new/litters/serializers.py†L1-L42】

---

## Moduł Posts

### `/posts/posts/`

Pełny CRUD na postach. W trakcie tworzenia autor ustawiany jest automatycznie na
bieżącego użytkownika. Dostępne filtry zapytania: `animal-id` oraz
`organization-id` (oba mogą współistnieć). W odpowiedziach widoczne są m.in.
`author`, `animal_name`, `organization_name`, powiązane `comments` i `reactions`.
Przy modyfikacji sprawdzane jest, czy użytkownik ma prawo edytować post
związany ze zwierzęciem (właściciel lub administrator).【F:django/gompet_new/posts/api_views.py†L1-L86】【F:django/gompet_new/posts/serializers.py†L1-L57】

**Ważne pola**: `content`, opcjonalnie `animal`, `organization`, `image`
(base64). Usuwanie jest dostępne tylko dla autora lub administratora.

---

## Moduł Articles

### `/articles/articles/`

CRUD na artykułach z mechanizmem „soft delete” (`DELETE` ustawia `deleted_at`).
Lista obsługuje paginację, sortowanie (`created_at`, `updated_at`), wyszukiwanie
po `title`, `content`, `author__username`, limit wyników (`limit`) oraz filtr
po imieniu autora (`author`).  Tworząc artykuł nie trzeba przekazywać pola
`author` – przypisywany jest zalogowany użytkownik. Odpowiedzi zawierają listy
powiązanych komentarzy i reakcji oraz znaczniki czasu.【F:django/gompet_new/articles/api_views.py†L1-L63】【F:django/gompet_new/articles/serializers.py†L1-L55】

