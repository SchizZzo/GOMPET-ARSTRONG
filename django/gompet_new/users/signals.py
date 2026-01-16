from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import MemberRole, Organization, OrganizationMember
from .role_permissions import sync_user_member_role_groups, sync_user_role_groups


@receiver(post_save, sender=Organization)
def ensure_owner_membership(
    sender,
    instance: Organization,
    created: bool,
    using: str | None = None,
    **kwargs,
) -> None:
    if not created or not instance.user_id:
        return

    def _create_owner_membership() -> None:
        OrganizationMember.objects.get_or_create(
            user=instance.user,
            organization=instance,
            defaults={
                "role": MemberRole.OWNER,
                "invitation_confirmed": True,
            },
        )
        sync_user_member_role_groups(instance.user, using=using)
        sync_user_role_groups(instance.user, using=using)

    transaction.on_commit(_create_owner_membership, using=using)
