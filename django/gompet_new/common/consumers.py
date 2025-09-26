"""Websocket consumer obsługujący licznik polubień."""

from __future__ import annotations

import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from .like_counter import ReactableRef, build_payload, make_group_name, resolve_content_type

logger = logging.getLogger(__name__)


class LikeCounterConsumer(AsyncJsonWebsocketConsumer):
    """Udostępnia liczbę polubień dla wskazanego obiektu."""

    content_type: ContentType
    reactable_id: int
    group_name: str

    async def connect(self) -> None:
        try:
            reactable_type = self.scope["url_route"]["kwargs"]["reactable_type"]
            reactable_id_raw = self.scope["url_route"]["kwargs"]["reactable_id"]
        except KeyError as exc:  # pragma: no cover - ochronny guard
            logger.warning("Brak wymaganych parametrów w ścieżce websocket: %s", exc)
            await self.close(code=4400)
            return

        try:
            self.reactable_id = int(reactable_id_raw)
        except (TypeError, ValueError):
            await self.close(code=4400)
            return

        try:
            self.content_type = await database_sync_to_async(resolve_content_type)(reactable_type)
        except ContentType.DoesNotExist:
            await self.close(code=4404)
            return

        self.group_name = make_group_name(self.content_type.pk, self.reactable_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_current_state()

    async def disconnect(self, code: int) -> None:  # noqa: D401 - API channels
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await super().disconnect(code)

    async def _send_current_state(self) -> None:
        payload = await database_sync_to_async(self._build_payload)()
        await self.send_json(payload)

    def _build_payload(self) -> dict[str, Any]:
        ref = ReactableRef(content_type=self.content_type, object_id=self.reactable_id)
        return build_payload(ref)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:  # pragma: no cover - API read-only
        raise ValidationError("Ten websocket służy wyłącznie do odczytu.")

    async def like_count_update(self, event: dict[str, Any]) -> None:
        await self.send_json(event["payload"])
