"""Real-time powiadomienia wysyłane przez websocket."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def make_user_group_name(user_id: int) -> str:
    """Zwraca nazwę grupy websocket dla użytkownika."""

    return f"notifications.user.{user_id}"


def broadcast_user_notification(user_id: int, payload: dict[str, Any]) -> bool:
    """Wysyła powiadomienie realtime do właściciela."""

    if not user_id:
        return False

    try:
        channel_layer = get_channel_layer()
    except (InvalidChannelLayerError, ImproperlyConfigured) as exc:
        logger.debug("Kanał warstwy websocket niedostępny: %s", exc)
        return False

    if channel_layer is None:
        return False

    group_name = make_user_group_name(user_id)

    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notification_message",
                "payload": payload,
            },
        )
    except TypeError as exc:
        logger.debug("Nie udało się wysłać powiadomienia: %s", exc, exc_info=True)
        return False

    return True


__all__ = [
    "broadcast_user_notification",
    "make_user_group_name",
]
