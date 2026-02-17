from typing import Iterable

from django.contrib.auth.models import Group, Permission

from .models import MemberRole, OrganizationMember, UserRole

ROLE_GROUP_PREFIX = "member_role_"
USER_ROLE_GROUP_PREFIX = "user_role_"

APP_MODELS = {
    "users": [
        "user",
        "organization",
        "organizationmember",
        "address",
        "species",
        "breedingtype",
        "breedingtypeorganizations",
    ],
    "animals": [
        "animal",
        "characteristics",
        "animalcharacteristic",
        "animalgallery",
        "animalparent",
        "animalsweightranges",
        "animalsbreedgroups",
    ],
    "posts": ["post"],
    "articles": ["article", "articlecategory"],
    "litters": ["litter", "litteranimal"],
    "common": ["comment", "reaction", "notification"],
}

ACTIONS_VIEW = ("view",)
ACTIONS_EDIT = ("add", "change", "view")
ACTIONS_FULL = ("add", "change", "delete", "view")

# Opis akcji (permissions):
# - ACTIONS_VIEW: tylko prawo do podglądu obiektów (read-only).
# - ACTIONS_EDIT: prawa do dodawania, edycji i podglądu (create/update/read).
# - ACTIONS_FULL: pełne prawa obejmujące tworzenie, edycję, usuwanie i podgląd (CRUD).


def _build_permissions(app_label: str, models: Iterable[str], actions: Iterable[str]) -> list[str]:
    return [f"{app_label}.{action}_{model}" for model in models for action in actions]


ALL_VIEW_PERMISSIONS = [
    permission
    for app_label, models in APP_MODELS.items()
    for permission in _build_permissions(app_label, models, ACTIONS_VIEW)
]

ALL_FULL_PERMISSIONS = [
    permission
    for app_label, models in APP_MODELS.items()
    for permission in _build_permissions(app_label, models, ACTIONS_FULL)
]

USERS_EDIT_PERMISSIONS = _build_permissions(
    "users",
    ["organization", "organizationmember", "address", "species", "breedingtype"],
    ACTIONS_EDIT,
)
USERS_ADMIN_PERMISSIONS = _build_permissions("users", ["user"], ACTIONS_FULL)
ANIMALS_EDIT_PERMISSIONS = _build_permissions("animals", APP_MODELS["animals"], ACTIONS_EDIT)
POSTS_EDIT_PERMISSIONS = _build_permissions("posts", APP_MODELS["posts"], ACTIONS_EDIT)
ARTICLES_EDIT_PERMISSIONS = _build_permissions("articles", APP_MODELS["articles"], ACTIONS_EDIT)
LITTERS_EDIT_PERMISSIONS = _build_permissions("litters", APP_MODELS["litters"], ACTIONS_EDIT)
COMMON_EDIT_PERMISSIONS = _build_permissions("common", ["comment", "reaction"], ACTIONS_EDIT)
COMMON_MODERATE_PERMISSIONS = _build_permissions(
    "common", ["comment", "reaction"], ("change", "delete", "view")
)
POSTS_MODERATE_PERMISSIONS = _build_permissions("posts", ["post"], ("change", "delete", "view"))


ROLE_PERMISSIONS = {
    # OWNER: pełne uprawnienia do wszystkich modeli aplikacji oraz
    # dodatkowe uprawnienia administracyjne do modelu użytkownika.
    MemberRole.OWNER: [
        *ALL_FULL_PERMISSIONS,
        *USERS_ADMIN_PERMISSIONS,
    ],
    # STAFF: dostęp do podglądu wszystkiego oraz prawa edycyjne do
    # użytkowników/organizacji, zwierząt, postów, artykułów, miotów i wspólnych zasobów.
    MemberRole.STAFF: [
        *ALL_VIEW_PERMISSIONS,
        *USERS_EDIT_PERMISSIONS,
        *ANIMALS_EDIT_PERMISSIONS,
        *POSTS_EDIT_PERMISSIONS,
        *ARTICLES_EDIT_PERMISSIONS,
        *LITTERS_EDIT_PERMISSIONS,
        *COMMON_EDIT_PERMISSIONS,
    ],
    # VOLUNTEER: tylko prawo do podglądu wszystkich zasobów.
    MemberRole.VOLUNTEER: [
        *ALL_VIEW_PERMISSIONS,
    ],
    # MODERATOR: prawo do podglądu oraz moderacji postów i komentarzy (zmiana/usuwanie).
    MemberRole.MODERATOR: [
        *ALL_VIEW_PERMISSIONS,
        *POSTS_MODERATE_PERMISSIONS,
        *COMMON_MODERATE_PERMISSIONS,
    ],
    # PARTNER: tylko prawo do podglądu wszystkich zasobów.
    MemberRole.PARTNER: [
        *ALL_VIEW_PERMISSIONS,
    ],
    # FINANCE: prawo do podglądu oraz edycji wybranych zasobów związanych z użytkownikami/organizacją.
    MemberRole.FINANCE: [
        *ALL_VIEW_PERMISSIONS,
        *USERS_EDIT_PERMISSIONS,
    ],
    # CONTENT: prawo do podglądu oraz edycji treści (posty i artykuły).
    MemberRole.CONTENT: [
        *ALL_VIEW_PERMISSIONS,
        *POSTS_EDIT_PERMISSIONS,
        *ARTICLES_EDIT_PERMISSIONS,
    ],
    # VIEWER: tylko prawo do podglądu wszystkich zasobów (read-only), podobne do VOLUNTEER.
    MemberRole.VIEWER: [
        *ALL_VIEW_PERMISSIONS,
    ],
}

# Basic user roles outside of organization membership.
USER_ROLE_PERMISSIONS = {
    "LIMITED": [
        *_build_permissions("users", ["organization"], ("add", "view")),
        *_build_permissions("animals", ["animal"], ("add", "change", "view")),
        *_build_permissions("posts", ["post"], ("add", "view")),
        *_build_permissions("articles", ["article"], ("add", "view")),
        *_build_permissions("litters", ["litter"], ("add", "view")),
        *_build_permissions("common", ["comment", "reaction"], ("add", "view", "change", "delete")),
        *_build_permissions("users", ["organizationmember"], ("add", "view")),
    ],
}


def member_role_group_name(role: str) -> str:
    return f"{ROLE_GROUP_PREFIX}{role}"


def user_role_group_name(role: str) -> str:
    return f"{USER_ROLE_GROUP_PREFIX}{role}"


def _resolve_permissions(permission_codes: Iterable[str], using: str | None = None):
    permissions = []
    for permission_code in permission_codes:
        app_label, codename = permission_code.split(".", maxsplit=1)
        permission = Permission.objects.using(using).filter(
            content_type__app_label=app_label,
            codename=codename,
        ).first()
        if permission:
            permissions.append(permission)
    return permissions


def ensure_member_role_groups(using: str | None = None) -> None:
    for role in MemberRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=member_role_group_name(role.value)
        )
        permissions = _resolve_permissions(ROLE_PERMISSIONS.get(role, []), using=using)
        group.permissions.set(permissions)


def ensure_user_role_groups(using: str | None = None) -> None:
    for role in UserRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=user_role_group_name(role.value)
        )
        permissions = _resolve_permissions(
            USER_ROLE_PERMISSIONS.get(role.value, []), using=using
        )
        group.permissions.set(permissions)


def sync_user_member_role_groups(user, using: str | None = None) -> None:
    ensure_member_role_groups(using=using)
    role_values = set(
        OrganizationMember.objects.using(using)
        .filter(user=user)
        .values_list("role", flat=True)
    )
    for role in MemberRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=member_role_group_name(role.value)
        )
        if role.value in role_values:
            user.groups.add(group)
        else:
            user.groups.remove(group)


def sync_user_role_groups(user, using: str | None = None) -> None:
    ensure_user_role_groups(using=using)
    for role in UserRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=user_role_group_name(role.value)
        )
        if user.role == role.value:
            user.groups.add(group)
        else:
            user.groups.remove(group)
