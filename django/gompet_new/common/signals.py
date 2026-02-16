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
from articles.models import Article
from posts.models import Post
from users.models import Organization

from .models import Comment, Follow, Notification, Reaction, ReactionType
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


@receiver(post_save, sender=Comment)
def handle_comment_saved(sender, instance: Comment, created: bool, **kwargs: Any) -> None:
    if not created:
        return

    notify_content_author_about_comment(instance)


@receiver(post_save, sender=Follow)
def handle_follow_saved(sender, instance: Follow, created: bool, **kwargs: Any) -> None:
    if not created:
        return

    notify_target_owner_about_follow(instance)


@receiver(post_save, sender=Post)
def handle_post_saved(sender, instance: Post, created: bool, **kwargs: Any) -> None:
    if not created:
        return

    notify_followers_about_new_post(instance)


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
        post_content_type = ContentType.objects.get_for_model(Post)
    except ContentType.DoesNotExist:
        return

    recipient = None
    target_type = None
    target_id = None

    if reaction.reactable_type_id == animal_content_type.id:
        try:
            animal = Animal.objects.get(pk=reaction.reactable_id)
        except Animal.DoesNotExist:
            return

        recipient = animal.owner
        target_type = "animal"
        target_id = animal.id
    elif reaction.reactable_type_id == post_content_type.id:
        try:
            post = Post.objects.get(pk=reaction.reactable_id)
        except Post.DoesNotExist:
            return

        recipient = post.author
        target_type = "post"
        target_id = post.id
    else:
        return

    if not recipient or recipient.id == reaction.user_id:
        return

    notification = Notification.objects.create(
        recipient=recipient,
        actor=reaction.user,
        verb="polubił(a)",
        target_type=target_type,
        target_id=target_id,
        created_object_id=reaction.id,
    )

    broadcast_user_notification(
        recipient.id, build_notification_payload(notification)
    )


def notify_content_author_about_comment(comment: Comment) -> None:
    if not comment.user_id:
        return

    try:
        article_content_type = ContentType.objects.get_for_model(Article)
        post_content_type = ContentType.objects.get_for_model(Post)
    except ContentType.DoesNotExist:
        return

    recipient = None
    target_type = None
    target_id = None

    if comment.content_type_id == post_content_type.id:
        try:
            post = Post.objects.get(pk=comment.object_id)
        except Post.DoesNotExist:
            return

        recipient = post.author
        target_type = "post"
        target_id = post.id
    elif comment.content_type_id == article_content_type.id:
        try:
            article = Article.objects.get(pk=comment.object_id)
        except Article.DoesNotExist:
            return

        recipient = article.author
        target_type = "article"
        target_id = article.id
    else:
        return

    if not recipient or recipient.id == comment.user_id:
        return

    notification = Notification.objects.create(
        recipient=recipient,
        actor=comment.user,
        verb="skomentował(a)",
        target_type=target_type,
        target_id=target_id,
        created_object_id=comment.id,
    )

    broadcast_user_notification(
        recipient.id, build_notification_payload(notification)
    )


def notify_target_owner_about_follow(follow: Follow) -> None:
    if not follow.user_id:
        return

    try:
        animal_content_type = ContentType.objects.get_for_model(Animal)
        organization_content_type = ContentType.objects.get_for_model(Organization)
    except ContentType.DoesNotExist:
        return

    recipient = None
    target_type = None
    target_id = None

    if follow.target_type_id == animal_content_type.id:
        try:
            animal = Animal.objects.get(pk=follow.target_id)
        except Animal.DoesNotExist:
            return

        recipient = animal.owner
        target_type = "animal"
        target_id = animal.id
    elif follow.target_type_id == organization_content_type.id:
        try:
            organization = Organization.objects.get(pk=follow.target_id)
        except Organization.DoesNotExist:
            return

        recipient = organization.user
        target_type = "organization"
        target_id = organization.id
    else:
        return

    if not recipient or recipient.id == follow.user_id:
        return

    notification = Notification.objects.create(
        recipient=recipient,
        actor=follow.user,
        verb="zaczął(a) obserwować",
        target_type=target_type,
        target_id=target_id,
        created_object_id=follow.id,
    )

    broadcast_user_notification(recipient.id, build_notification_payload(notification))


def notify_followers_about_new_post(post: Post) -> None:
    actor = post.author
    if not actor:
        return

    try:
        animal_content_type = ContentType.objects.get_for_model(Animal)
        organization_content_type = ContentType.objects.get_for_model(Organization)
    except ContentType.DoesNotExist:
        return

    target_type = None
    target_id = None
    follow_qs = Follow.objects.none()

    if post.animal_id:
        target_type = "animal"
        target_id = post.animal_id
        follow_qs = Follow.objects.filter(
            target_type=animal_content_type,
            target_id=post.animal_id,
            notification_preferences__posts=True,
        )
    elif post.organization_id:
        target_type = "organization"
        target_id = post.organization_id
        follow_qs = Follow.objects.filter(
            target_type=organization_content_type,
            target_id=post.organization_id,
            notification_preferences__posts=True,
        )

    if target_type is None or target_id is None:
        return

    recipient_ids = list(
        follow_qs.exclude(user_id=actor.id).values_list("user_id", flat=True).distinct()
    )

    if not recipient_ids:
        return

    for recipient_id in recipient_ids:
        notification = Notification.objects.create(
            recipient_id=recipient_id,
            actor=actor,
            verb="dodał(a) nowy post",
            target_type=target_type,
            target_id=target_id,
            created_object_id=post.id,
        )
        broadcast_user_notification(recipient_id, build_notification_payload(notification))


__all__ = ["broadcast_like_count"]
