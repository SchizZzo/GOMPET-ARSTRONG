"""Helpers obsługujące licznik reakcji typu LIKE."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet

from .models import Reaction, ReactionType


@dataclass(slots=True)
class ReactableRef:
    """Reprezentuje obiekt, dla którego liczymy reakcje."""

    content_type: ContentType
    object_id: int

    @property
    def natural_key(self) -> str:
        return f"{self.content_type.app_label}.{self.content_type.model}"


def resolve_content_type(value: Any) -> ContentType:
    """Zwraca ``ContentType`` niezależnie od tego jaką postać przyjmie ``value``."""

    if isinstance(value, ContentType):
        return value

    if isinstance(value, int):
        return ContentType.objects.get(pk=value)

    if isinstance(value, str):
        if value.isdigit():
            return ContentType.objects.get(pk=int(value))
        if "." in value:
            app_label, model = value.split(".", 1)
            return ContentType.objects.get(app_label=app_label, model=model)

    raise ContentType.DoesNotExist(value)


def like_queryset(ref: ReactableRef) -> QuerySet[Reaction]:
    """Queryset z wszystkimi reakcjami LIKE dla wskazanego obiektu."""

    return Reaction.objects.filter(
        reactable_type=ref.content_type,
        reactable_id=ref.object_id,
        reaction_type=ReactionType.LIKE,
    )


def calculate_like_total(ref: ReactableRef) -> int:
    """Zwraca liczbę reakcji LIKE."""

    return like_queryset(ref).count()


def make_group_name(content_type_id: int, object_id: int) -> str:
    """Kanał grupowy używany do wysyłki aktualizacji liczby polubień."""

    return f"like_counter:{content_type_id}:{object_id}"


def build_payload(ref: ReactableRef) -> dict[str, Any]:
    """Sformatowany payload do wysłania przez websocket."""

    return {
        "reactable": {
            "id": ref.object_id,
            "type": ref.natural_key,
        },
        "total_likes": calculate_like_total(ref),
    }


__all__ = [
    "ReactableRef",
    "resolve_content_type",
    "calculate_like_total",
    "make_group_name",
    "build_payload",
]
