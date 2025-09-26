from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "common"

    def ready(self) -> None:  # pragma: no cover - import side effects only
        # Importujemy sygnały przy starcie aplikacji aby zapewnić rejestrację
        # nasłuchiwaczy post_save/post_delete dla modelu Reaction.
        from . import signals  # noqa: F401

        return super().ready()
