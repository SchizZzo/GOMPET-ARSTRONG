from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from animals.models import Animal, Gender, Size
from common.like_counter import ReactableRef, build_payload, make_group_name, resolve_content_type
from common.models import Reaction, ReactionType
from common.signals import broadcast_like_count


class LikeCounterHelpersTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="secret",
            first_name="Jane",
            last_name="Doe",
        )
        self.animal = Animal.objects.create(
            name="Burek",
            species="dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
        )
        self.content_type = ContentType.objects.get_for_model(Animal)

    def test_make_group_name(self) -> None:
        group = make_group_name(self.content_type.id, self.animal.id)
        self.assertEqual(group, f"like_counter.{self.content_type.id}.{self.animal.id}")

    def test_resolve_content_type_accepts_natural_key(self) -> None:
        value = f"{self.content_type.app_label}.{self.content_type.model}"
        resolved = resolve_content_type(value)
        self.assertEqual(resolved, self.content_type)

    def test_build_payload_counts_likes(self) -> None:
        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        ref = ReactableRef(content_type=self.content_type, object_id=self.animal.id)
        payload = build_payload(ref)

        self.assertEqual(payload["total_likes"], 1)
        self.assertEqual(payload["reactable"], {
            "id": self.animal.id,
            "type": f"{self.content_type.app_label}.{self.content_type.model}",
        })

    @mock.patch("common.signals.get_channel_layer")
    def test_broadcast_like_count_sends_payload(self, mocked_layer_getter: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.user,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        mocked_layer = mock.Mock()
        mocked_layer.group_send = mock.AsyncMock()
        mocked_layer_getter.return_value = mocked_layer

        sent = broadcast_like_count(self.content_type, self.animal.id)

        self.assertTrue(sent)
        mocked_layer.group_send.assert_awaited_once()
        args, _ = mocked_layer.group_send.await_args
        self.assertEqual(args[1]["payload"]["total_likes"], 1)

    @mock.patch("common.signals.get_channel_layer", return_value=None)
    def test_broadcast_like_count_returns_false_without_layer(self, mocked_layer_getter: mock.Mock) -> None:
        self.assertFalse(broadcast_like_count(self.content_type, self.animal.id))
