"""Real-time powiadomienia wysyłane przez websocket."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer
from django.core.exceptions import ImproperlyConfigured

from animals.models import Animal
from common.models import Notification

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


def _get_target_label(notification: Notification) -> str | None:
    if notification.target_type != "animal":
        return None

    try:
        animal = Animal.objects.only("name").get(pk=notification.target_id)
    except Animal.DoesNotExist:
        return None

    return animal.name


def build_notification_payload(
    notification: Notification,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = notification.actor
    target_label = _get_target_label(notification)
    origin_label = target_label or notification.target_type
    notification_type = "unknown"
    if (
        notification.target_type == "organization"
        and notification.verb == "przyjął(a) Cię do organizacji"
    ):
        notification_type = "organization_invite_accepted"
    payload = {
        "id": notification.id,
        "actor": {
            "id": actor.id,
            "first_name": actor.first_name,
            "last_name": actor.last_name,
            "email": actor.email,
        },
        "verb": notification.verb,
        "target_type": notification.target_type,
        "target_id": notification.target_id,
        "created_object_id": notification.created_object_id,
        "target_label": target_label,
        "origin": {
            "type": notification.target_type,
            "id": notification.target_id,
            "label": origin_label,
        },
        "type": notification_type,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
    }
    if extra_payload:
        payload.update(extra_payload)
    return payload


__all__ = [
    "broadcast_user_notification",
    "build_notification_payload",
    "make_user_group_name",
]
