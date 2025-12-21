"""Konfiguracja ASGI z obsługą kanałów websocket."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gompet_new.settings")

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from common import routing as common_routing
from gompet_new.middleware import JWTAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(common_routing.websocket_urlpatterns)
        ),
    }
)

__all__ = ["application"]
