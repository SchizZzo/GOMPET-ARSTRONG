"""Ścieżki websocket dla aplikacji ``common``."""

from __future__ import annotations

from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    re_path(
        r"^ws/reactable/(?P<reactable_type>[^/]+)/(?P<reactable_id>\d+)/$",
        consumers.LikeCounterConsumer.as_asgi(),
        name="like-counter",
    ),
]


__all__ = ["websocket_urlpatterns"]
