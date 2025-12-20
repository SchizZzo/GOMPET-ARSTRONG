from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from animals.models import Animal, Gender, Size
from common.models import Reaction, ReactionType
from common.notifications import broadcast_user_notification, make_user_group_name


class NotificationHelpersTests(TestCase):
    @mock.patch("common.notifications.get_channel_layer")
    def test_broadcast_user_notification_sends_payload(self, mocked_layer_getter: mock.Mock) -> None:
        mocked_layer = mock.Mock()
        mocked_layer.group_send = mock.AsyncMock()
        mocked_layer_getter.return_value = mocked_layer

        payload = {"foo": "bar"}
        sent = broadcast_user_notification(5, "dummy.event", payload)

        self.assertTrue(sent)
        mocked_layer.group_send.assert_awaited_once()
        args, _ = mocked_layer.group_send.await_args
        self.assertEqual(args[0], make_user_group_name(5))
        self.assertEqual(args[1]["event"], "dummy.event")
        self.assertEqual(args[1]["payload"], payload)


class NotificationSignalTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="owner@example.com",
            password="secret",
            first_name="Owner",
            last_name="User",
        )
        self.liker = User.objects.create_user(
            email="fan@example.com",
            password="secret",
            first_name="Fan",
            last_name="User",
        )
        self.animal = Animal.objects.create(
            name="Burek",
            species="dog",
            gender=Gender.MALE,
            size=Size.MEDIUM,
            owner=self.owner,
        )
        self.content_type = ContentType.objects.get_for_model(Animal)

    @mock.patch("common.signals.broadcast_user_notification")
    def test_like_on_animal_notifies_owner(self, mocked_broadcast: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.liker,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        mocked_broadcast.assert_called_once()
        owner_id, event, payload = mocked_broadcast.call_args.args
        self.assertEqual(owner_id, self.owner.id)
        self.assertEqual(event, "animal_liked")
        self.assertEqual(payload["animal_id"], self.animal.id)
        self.assertEqual(payload["liked_by"], self.liker.id)

    @mock.patch("common.signals.broadcast_user_notification")
    def test_owner_like_is_not_notified(self, mocked_broadcast: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.owner,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        mocked_broadcast.assert_not_called()
