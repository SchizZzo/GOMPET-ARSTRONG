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
ACTIONS_MODERATE = ("change", "delete", "view")
ACTIONS_FULL = ("add", "change", "delete", "view")


def _build_permissions(
    app_label: str,
    models: Iterable[str],
    actions: Iterable[str],
) -> list[str]:
    return [
        f"{app_label}.{action}_{model}"
        for model in models
        for action in actions
    ]


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


ORGANIZATION_VIEW_PERMISSIONS = _build_permissions(
    "users",
    [
        "organization",
        "address",
        "species",
        "breedingtype",
        "breedingtypeorganizations",
    ],
    ACTIONS_VIEW,
)

ORGANIZATION_EDIT_PERMISSIONS = _build_permissions(
    "users",
    [
        "organization",
        "address",
        "breedingtype",
        "breedingtypeorganizations",
    ],
    ACTIONS_EDIT,
)

ORGANIZATION_FULL_PERMISSIONS = _build_permissions(
    "users",
    [
        "organization",
        "address",
        "breedingtype",
        "breedingtypeorganizations",
    ],
    ACTIONS_FULL,
)

ORGANIZATION_MEMBERS_VIEW_PERMISSIONS = _build_permissions(
    "users",
    ["organizationmember"],
    ACTIONS_VIEW,
)

ORGANIZATION_MEMBERS_EDIT_PERMISSIONS = _build_permissions(
    "users",
    ["organizationmember"],
    ACTIONS_EDIT,
)

ORGANIZATION_MEMBERS_FULL_PERMISSIONS = _build_permissions(
    "users",
    ["organizationmember"],
    ACTIONS_FULL,
)

USERS_VIEW_PERMISSIONS = _build_permissions(
    "users",
    ["user"],
    ACTIONS_VIEW,
)

USERS_ADMIN_PERMISSIONS = _build_permissions(
    "users",
    ["user"],
    ACTIONS_FULL,
)


ANIMALS_VIEW_PERMISSIONS = _build_permissions(
    "animals",
    APP_MODELS["animals"],
    ACTIONS_VIEW,
)

ANIMALS_EDIT_PERMISSIONS = _build_permissions(
    "animals",
    APP_MODELS["animals"],
    ACTIONS_EDIT,
)

ANIMALS_FULL_PERMISSIONS = _build_permissions(
    "animals",
    APP_MODELS["animals"],
    ACTIONS_FULL,
)

ANIMAL_GALLERY_EDIT_PERMISSIONS = _build_permissions(
    "animals",
    ["animalgallery"],
    ACTIONS_EDIT,
)


LITTERS_VIEW_PERMISSIONS = _build_permissions(
    "litters",
    APP_MODELS["litters"],
    ACTIONS_VIEW,
)

LITTERS_EDIT_PERMISSIONS = _build_permissions(
    "litters",
    APP_MODELS["litters"],
    ACTIONS_EDIT,
)

LITTERS_FULL_PERMISSIONS = _build_permissions(
    "litters",
    APP_MODELS["litters"],
    ACTIONS_FULL,
)


POSTS_VIEW_PERMISSIONS = _build_permissions(
    "posts",
    ["post"],
    ACTIONS_VIEW,
)

POSTS_CREATE_EDIT_PERMISSIONS = _build_permissions(
    "posts",
    ["post"],
    ACTIONS_EDIT,
)

POSTS_FULL_PERMISSIONS = _build_permissions(
    "posts",
    ["post"],
    ACTIONS_FULL,
)

POSTS_MODERATE_PERMISSIONS = _build_permissions(
    "posts",
    ["post"],
    ACTIONS_MODERATE,
)


ARTICLES_VIEW_PERMISSIONS = _build_permissions(
    "articles",
    APP_MODELS["articles"],
    ACTIONS_VIEW,
)

ARTICLES_EDIT_PERMISSIONS = _build_permissions(
    "articles",
    APP_MODELS["articles"],
    ACTIONS_EDIT,
)

ARTICLES_FULL_PERMISSIONS = _build_permissions(
    "articles",
    APP_MODELS["articles"],
    ACTIONS_FULL,
)


COMMON_VIEW_PERMISSIONS = _build_permissions(
    "common",
    APP_MODELS["common"],
    ACTIONS_VIEW,
)

COMMENTS_REACTIONS_CREATE_EDIT_PERMISSIONS = _build_permissions(
    "common",
    ["comment", "reaction"],
    ACTIONS_EDIT,
)

COMMENTS_REACTIONS_MODERATE_PERMISSIONS = _build_permissions(
    "common",
    ["comment", "reaction"],
    ACTIONS_MODERATE,
)

NOTIFICATIONS_VIEW_PERMISSIONS = _build_permissions(
    "common",
    ["notification"],
    ACTIONS_VIEW,
)


PUBLIC_VIEW_PERMISSIONS = [
    *ORGANIZATION_VIEW_PERMISSIONS,
    *ANIMALS_VIEW_PERMISSIONS,
    *LITTERS_VIEW_PERMISSIONS,
    *POSTS_VIEW_PERMISSIONS,
    *ARTICLES_VIEW_PERMISSIONS,
    *_build_permissions("common", ["comment", "reaction"], ACTIONS_VIEW),
]


PARTNER_VIEW_PERMISSIONS = [
    *PUBLIC_VIEW_PERMISSIONS,
    *ORGANIZATION_MEMBERS_VIEW_PERMISSIONS,
    *USERS_VIEW_PERMISSIONS,
    *NOTIFICATIONS_VIEW_PERMISSIONS,
]


ROLE_PERMISSIONS = {
    MemberRole.OWNER: [
        *PUBLIC_VIEW_PERMISSIONS,
        *ORGANIZATION_FULL_PERMISSIONS,
        *ORGANIZATION_MEMBERS_FULL_PERMISSIONS,
        *ANIMALS_FULL_PERMISSIONS,
        *LITTERS_FULL_PERMISSIONS,
        *POSTS_FULL_PERMISSIONS,
        *ARTICLES_FULL_PERMISSIONS,
        *COMMENTS_REACTIONS_MODERATE_PERMISSIONS,
        *USERS_VIEW_PERMISSIONS,
        *NOTIFICATIONS_VIEW_PERMISSIONS,
    ],
    MemberRole.STAFF: [
        *PUBLIC_VIEW_PERMISSIONS,
        *ANIMALS_EDIT_PERMISSIONS,
        *LITTERS_EDIT_PERMISSIONS,
        *POSTS_CREATE_EDIT_PERMISSIONS,
        *COMMENTS_REACTIONS_CREATE_EDIT_PERMISSIONS,
    ],
    MemberRole.MODERATOR: [
        *PUBLIC_VIEW_PERMISSIONS,
        *POSTS_MODERATE_PERMISSIONS,
        *COMMENTS_REACTIONS_MODERATE_PERMISSIONS,
        *USERS_VIEW_PERMISSIONS,
    ],
    MemberRole.CONTENT: [
        *PUBLIC_VIEW_PERMISSIONS,
        *POSTS_CREATE_EDIT_PERMISSIONS,
        *ANIMAL_GALLERY_EDIT_PERMISSIONS,
        *COMMENTS_REACTIONS_CREATE_EDIT_PERMISSIONS,
    ],
    MemberRole.VOLUNTEER: [
        *PUBLIC_VIEW_PERMISSIONS,
        *POSTS_CREATE_EDIT_PERMISSIONS,
        *ANIMAL_GALLERY_EDIT_PERMISSIONS,
    ],
    MemberRole.PARTNER: [
        *PARTNER_VIEW_PERMISSIONS,
    ],
    MemberRole.VIEWER: [
        *PUBLIC_VIEW_PERMISSIONS,
    ],
}


USER_ROLE_PERMISSIONS = {
    UserRole.LIMITED.value: [
        *_build_permissions("users", ["organization"], ("add", "view")),
        *_build_permissions("users", ["organizationmember"], ("add", "view")),
        *_build_permissions("animals", ["animal"], ("add", "change", "view")),
        *_build_permissions("posts", ["post"], ("add", "change", "view")),
        *_build_permissions("articles", ["article"], ("add", "change", "view")),
        *_build_permissions("litters", ["litter"], ("add", "view")),
        *_build_permissions("common", ["comment", "reaction"], ("add", "change", "view")),
    ],
}


def member_role_group_name(role: str) -> str:
    return f"{ROLE_GROUP_PREFIX}{role}"


def user_role_group_name(role: str) -> str:
    return f"{USER_ROLE_GROUP_PREFIX}{role}"


def _resolve_permissions(
    permission_codes: Iterable[str],
    using: str | None = None,
) -> list[Permission]:
    permissions = []

    for permission_code in permission_codes:
        app_label, codename = permission_code.split(".", maxsplit=1)

        permission = (
            Permission.objects.using(using)
            .filter(
                content_type__app_label=app_label,
                codename=codename,
            )
            .first()
        )

        if permission:
            permissions.append(permission)

    return permissions


def ensure_member_role_groups(using: str | None = None) -> None:
    for role in MemberRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=member_role_group_name(role.value)
        )

        permissions = _resolve_permissions(
            ROLE_PERMISSIONS.get(role, []),
            using=using,
        )

        group.permissions.set(permissions)


def ensure_user_role_groups(using: str | None = None) -> None:
    for role in UserRole:
        group, _ = Group.objects.using(using).get_or_create(
            name=user_role_group_name(role.value)
        )

        permissions = _resolve_permissions(
            USER_ROLE_PERMISSIONS.get(role.value, []),
            using=using,
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
