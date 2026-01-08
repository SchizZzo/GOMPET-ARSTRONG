from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .role_permissions import ensure_member_role_groups


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self) -> None:
        post_migrate.connect(
            create_member_role_groups,
            sender=self,
            dispatch_uid="users.ensure_member_role_groups",
        )


def create_member_role_groups(**kwargs) -> None:
    ensure_member_role_groups(using=kwargs.get("using"))
