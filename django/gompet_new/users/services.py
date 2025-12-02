from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import MemberRole

User = get_user_model()


class CannotDeleteUser(Exception):
    """Raised when a user cannot be safely removed."""


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

    Token.objects.filter(user=user).delete()

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
