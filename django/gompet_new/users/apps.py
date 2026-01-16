from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self) -> None:
        from . import signals

        post_migrate.connect(
            create_member_role_groups,
            sender=self,
            dispatch_uid="users.ensure_member_role_groups",
        )


def create_member_role_groups(**kwargs) -> None:
    from .role_permissions import ensure_member_role_groups

    ensure_member_role_groups(using=kwargs.get("using"))
