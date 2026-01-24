from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone
from importlib import util

from .models import MemberRole, Organization, OrganizationMember
from .role_permissions import sync_user_member_role_groups, sync_user_role_groups

User = get_user_model()


class CannotDeleteUser(Exception):
    """Raised when a user cannot be safely removed."""


def _delete_authtoken_tokens(user: User) -> None:
    """Delete tokens from DRF's TokenAuthentication if available."""

    if util.find_spec("rest_framework.authtoken.models") is None:
        return

    from rest_framework.authtoken.models import Token

    if hasattr(Token, "objects"):
        Token.objects.filter(user=user).delete()


def _blacklist_jwt_tokens(user: User) -> None:
    """Blacklist and remove SimpleJWT outstanding tokens if enabled."""

    if "rest_framework_simplejwt.token_blacklist" not in settings.INSTALLED_APPS:
        return

    if util.find_spec("rest_framework_simplejwt.token_blacklist.models") is None:
        return

    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    tokens = OutstandingToken.objects.filter(user=user)
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
    tokens.delete()


@transaction.atomic
def delete_user_account(user: User):
    """Soft-delete and anonymize a user while preserving related content."""
    owned_orgs = user.organizations.all()

    for org in owned_orgs:
        other_owners = org.members.filter(role=MemberRole.OWNER).exclude(user_id=user.id)
        if not other_owners.exists():
            raise CannotDeleteUser(
                f"Użytkownik jest jedynym właścicielem organizacji {org.name}"
            )

    _delete_authtoken_tokens(user)
    _blacklist_jwt_tokens(user)

    for session in Session.objects.all():
        data = session.get_decoded()
        if data.get("_auth_user_id") == str(user.id):
            session.delete()

    user.email = f"deleted_{user.id}@example.invalid"
    user.first_name = ""
    user.last_name = ""
    user.phone = ""
    user.image = ""
    user.location = None
    user.is_active = False
    user.is_deleted = True
    user.deleted_at = timezone.now()
    user.save(
        update_fields=[
            "email",
            "first_name",
            "last_name",
            "phone",
            "image",
            "location",
            "is_active",
            "is_deleted",
            "deleted_at",
        ]
    )


@transaction.atomic
def transfer_organization_owner(
    organization: Organization,
    new_owner: User,
    *,
    using: str | None = None,
) -> Organization:
    """Transfer organization ownership and synchronize memberships."""
    previous_owner = organization.user
    if previous_owner and previous_owner.id == new_owner.id:
        return organization

    organization.user = new_owner
    organization.save(update_fields=["user"])

    membership, _ = OrganizationMember.objects.get_or_create(
        user=new_owner,
        organization=organization,
        defaults={
            "role": MemberRole.OWNER,
            "invitation_confirmed": True,
        },
    )
    if membership.role != MemberRole.OWNER:
        membership.role = MemberRole.OWNER
        membership.invitation_confirmed = True
        membership.save(update_fields=["role", "invitation_confirmed"])

    if previous_owner and previous_owner.id != new_owner.id:
        previous_membership = OrganizationMember.objects.filter(
            user=previous_owner,
            organization=organization,
        ).first()
        if previous_membership and previous_membership.role == MemberRole.OWNER:
            previous_membership.role = MemberRole.STAFF
            previous_membership.save(update_fields=["role"])
            sync_user_member_role_groups(previous_owner, using=using)
            sync_user_role_groups(previous_owner, using=using)

    sync_user_member_role_groups(new_owner, using=using)
    sync_user_role_groups(new_owner, using=using)

    return organization
