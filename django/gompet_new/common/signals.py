"""Sygnały aktualizujące licznik polubień."""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ImproperlyConfigured
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from animals.models import Animal
from .like_counter import ReactableRef, build_payload, make_group_name, resolve_content_type
from .models import Notification, Reaction, ReactionType
from .notifications import broadcast_user_notification, build_notification_payload

logger = logging.getLogger(__name__)


def broadcast_like_count(reactable_type: Any, reactable_id: int) -> bool:
    """Wysyła aktualną liczbę polubień do odpowiedniej grupy websocket."""

    try:
        content_type = resolve_content_type(reactable_type)
    except ContentType.DoesNotExist:
        logger.warning("Nie znaleziono ContentType dla wartości %s", reactable_type)
        return False

    ref = ReactableRef(content_type=content_type, object_id=reactable_id)
    payload = build_payload(ref)

    try:
        channel_layer = get_channel_layer()
    except (InvalidChannelLayerError, ImproperlyConfigured) as exc:
        logger.debug("Kanał warstwy websocket niedostępny: %s", exc)
        return False

    if channel_layer is None:
        return False

    group_name = make_group_name(content_type.pk, reactable_id)
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "like_count_update",
                "payload": payload,
            },
        )
    except TypeError as exc:
        logger.debug(
            "Nie udało się wysłać aktualizacji licznika polubień: %s",
            exc,
            exc_info=True,
        )
        return False

    return True


@receiver(pre_save, sender=Reaction)
def remember_previous_reaction_type(sender, instance: Reaction, **kwargs: Any) -> None:
    if not instance.pk:
        instance._previous_reaction_type = None
        return

    try:
        previous = Reaction.objects.get(pk=instance.pk)
    except Reaction.DoesNotExist:
        instance._previous_reaction_type = None
    else:
        instance._previous_reaction_type = previous.reaction_type


@receiver(post_save, sender=Reaction)
def handle_reaction_saved(sender, instance: Reaction, **kwargs: Any) -> None:
    previous_type = getattr(instance, "_previous_reaction_type", None)

    if instance.reaction_type == ReactionType.LIKE or previous_type == ReactionType.LIKE:
        broadcast_like_count(instance.reactable_type, instance.reactable_id)

    notify_owner_about_like(instance, previous_type)

    if hasattr(instance, "_previous_reaction_type"):
        delattr(instance, "_previous_reaction_type")


@receiver(post_delete, sender=Reaction)
def handle_reaction_deleted(sender, instance: Reaction, **kwargs: Any) -> None:
    if instance.reaction_type == ReactionType.LIKE:
        broadcast_like_count(instance.reactable_type, instance.reactable_id)


def notify_owner_about_like(reaction: Reaction, previous_type: ReactionType | None = None) -> None:
    if reaction.reaction_type != ReactionType.LIKE:
        return

    if previous_type == ReactionType.LIKE:
        return

    if not reaction.user_id:
        return

    try:
        animal_content_type = ContentType.objects.get_for_model(Animal)
    except ContentType.DoesNotExist:
        return

    if reaction.reactable_type_id != animal_content_type.id:
        return

    try:
        animal = Animal.objects.get(pk=reaction.reactable_id)
    except Animal.DoesNotExist:
        return

    if not animal.owner_id or animal.owner_id == reaction.user_id:
        return

    notification = Notification.objects.create(
        recipient=animal.owner,
        actor=reaction.user,
        verb="polubił(a)",
        target_type="animal",
        target_id=animal.id,
    )

    broadcast_user_notification(
        animal.owner_id, build_notification_payload(notification)
    )


__all__ = ["broadcast_like_count"]
