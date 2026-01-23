from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from animals.models import Animal, Gender, Size
from common.consumers import NotificationConsumer
from common.models import Notification, Reaction, ReactionType
from common.notifications import (
    broadcast_user_notification,
    build_notification_payload,
    make_user_group_name,
)
from channels.testing import WebsocketCommunicator
from asgiref.sync import async_to_sync
from rest_framework.test import APIClient
from gompet_new.middleware import JWTAuthMiddleware, JWTAuthMiddlewareStack
from posts.models import Post


class NotificationHelpersTests(TestCase):
    @mock.patch("common.notifications.get_channel_layer")
    def test_broadcast_user_notification_sends_payload(self, mocked_layer_getter: mock.Mock) -> None:
        mocked_layer = mock.Mock()
        mocked_layer.group_send = mock.AsyncMock()
        mocked_layer_getter.return_value = mocked_layer

        payload = {"foo": "bar"}
        sent = broadcast_user_notification(5, payload)

        self.assertTrue(sent)
        mocked_layer.group_send.assert_awaited_once()
        args, _ = mocked_layer.group_send.await_args
        self.assertEqual(args[0], make_user_group_name(5))
        self.assertEqual(args[1]["payload"], payload)

    def test_build_notification_payload_serializes_fields(self) -> None:
        User = get_user_model()
        recipient = User.objects.create_user(email="to@example.com", password="secret")
        actor = User.objects.create_user(
            email="from@example.com",
            password="secret",
            first_name="From",
            last_name="User",
        )
        notification = Notification.objects.create(
            recipient=recipient,
            actor=actor,
            verb="polubił(a)",
            target_type="animal",
            target_id=1,
        )

        payload = build_notification_payload(notification)

        self.assertEqual(payload["id"], notification.id)
        self.assertEqual(payload["actor"]["id"], actor.id)
        self.assertEqual(payload["verb"], "polubił(a)")
        self.assertEqual(payload["target_type"], "animal")
        self.assertEqual(payload["target_id"], 1)
        self.assertIsNone(payload["created_object_id"])
        self.assertEqual(payload["type"], "unknown")


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
        self.post = Post.objects.create(
            content="Testowy post",
            author=self.owner,
            animal=self.animal,
        )
        self.content_type = ContentType.objects.get_for_model(Animal)
        self.post_content_type = ContentType.objects.get_for_model(Post)

    @mock.patch("common.signals.broadcast_user_notification")
    def test_like_on_animal_notifies_owner(self, mocked_broadcast: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.liker,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        notification = Notification.objects.get(recipient=self.owner)

        mocked_broadcast.assert_called_once()
        owner_id, payload = mocked_broadcast.call_args.args
        self.assertEqual(owner_id, self.owner.id)
        self.assertEqual(payload["id"], notification.id)
        self.assertEqual(payload["target_id"], self.animal.id)
        self.assertEqual(payload["actor"]["id"], self.liker.id)
        self.assertEqual(payload["verb"], "polubił(a)")

    @mock.patch("common.signals.broadcast_user_notification")
    def test_owner_like_is_not_notified(self, mocked_broadcast: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.owner,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.content_type,
            reactable_id=self.animal.id,
        )

        mocked_broadcast.assert_not_called()

        self.assertFalse(Notification.objects.filter(recipient=self.owner).exists())

    @mock.patch("common.signals.broadcast_user_notification")
    def test_like_on_post_notifies_author(self, mocked_broadcast: mock.Mock) -> None:
        Reaction.objects.create(
            user=self.liker,
            reaction_type=ReactionType.LIKE,
            reactable_type=self.post_content_type,
            reactable_id=self.post.id,
        )

        notification = Notification.objects.get(recipient=self.owner)

        mocked_broadcast.assert_called_once()
        author_id, payload = mocked_broadcast.call_args.args
        self.assertEqual(author_id, self.owner.id)
        self.assertEqual(payload["id"], notification.id)
        self.assertEqual(payload["target_id"], self.post.id)
        self.assertEqual(payload["actor"]["id"], self.liker.id)
        self.assertEqual(payload["verb"], "polubił(a)")


class NotificationApiTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="secret",
            first_name="Jane",
            last_name="Doe",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="secret",
            first_name="John",
            last_name="Roe",
        )
        self.client = APIClient()

    def test_list_returns_only_user_notifications(self) -> None:
        first = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            verb="polubił(a)",
            target_type="animal",
            target_id=7,
        )
        Notification.objects.create(
            recipient=self.other_user,
            actor=self.user,
            verb="polubił(a)",
            target_type="animal",
            target_id=9,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], first.id)
        self.assertEqual(response.data[0]["actor"]["id"], self.other_user.id)

    def test_patch_allows_marking_as_read(self) -> None:
        notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            verb="polubił(a)",
            target_type="animal",
            target_id=7,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("notification-detail", args=[notification.id])
        response = self.client.patch(url, {"is_read": True}, format="json")

        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_patch_rejects_other_fields(self) -> None:
        notification = Notification.objects.create(
            recipient=self.user,
            actor=self.other_user,
            verb="polubił(a)",
            target_type="animal",
            target_id=7,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("notification-detail", args=[notification.id])
        response = self.client.patch(url, {"verb": "edited"}, format="json")

        self.assertEqual(response.status_code, 400)


class NotificationConsumerTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="secret",
            first_name="Jane",
            last_name="Doe",
        )

    def test_anonymous_user_is_rejected(self) -> None:
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            "/ws/notifications/1/",
        )

        connected, _ = async_to_sync(communicator.connect)()

        self.assertFalse(connected)
        self.assertEqual(communicator.close_code, 4401)

    def test_authenticated_user_receives_messages(self) -> None:
        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            f"/ws/notifications/{self.user.id}/",
        )
        communicator.scope["user"] = self.user

        connected, _ = async_to_sync(communicator.connect)()

        self.assertTrue(connected)

        async_to_sync(communicator.application_instance.channel_layer.group_send)(
            make_user_group_name(self.user.id),
            {"type": "notification_message", "payload": {"hello": "world"}},
        )

        response = async_to_sync(communicator.receive_json_from)()
        self.assertEqual(response, {"hello": "world"})

        async_to_sync(communicator.disconnect)()

    def test_jwt_authenticated_user_receives_messages(self) -> None:
        access_token = AccessToken.for_user(self.user)
        communicator = WebsocketCommunicator(
            JWTAuthMiddleware(NotificationConsumer.as_asgi()),
            f"/ws/notifications/{self.user.id}/?token={access_token}",
        )

        connected, _ = async_to_sync(communicator.connect)()

        self.assertTrue(connected)

        async_to_sync(communicator.application_instance.channel_layer.group_send)(
            make_user_group_name(self.user.id),
            {"type": "notification_message", "payload": {"hello": "jwt"}},
        )

        response = async_to_sync(communicator.receive_json_from)()
        self.assertEqual(response, {"hello": "jwt"})

        async_to_sync(communicator.disconnect)()

    def test_authenticated_user_cannot_subscribe_to_other_user(self) -> None:
        other_user = get_user_model().objects.create_user(
            email="other@example.com",
            password="secret",
            first_name="John",
            last_name="Smith",
        )

        communicator = WebsocketCommunicator(
            NotificationConsumer.as_asgi(),
            f"/ws/notifications/{other_user.id}/",
        )
        communicator.scope["user"] = self.user

        connected, _ = async_to_sync(communicator.connect)()

        self.assertFalse(connected)
        self.assertEqual(communicator.close_code, 4403)

    def test_session_authenticated_user_receives_messages(self) -> None:
        self.client.force_login(self.user)
        session_id = self.client.cookies["sessionid"].value

        communicator = WebsocketCommunicator(
            JWTAuthMiddlewareStack(NotificationConsumer.as_asgi()),
            f"/ws/notifications/{self.user.id}/",
            headers=[(b"cookie", f"sessionid={session_id}".encode())],
        )

        connected, _ = async_to_sync(communicator.connect)()

        self.assertTrue(connected)

        async_to_sync(communicator.application_instance.channel_layer.group_send)(
            make_user_group_name(self.user.id),
            {"type": "notification_message", "payload": {"hello": "session"}},
        )

        response = async_to_sync(communicator.receive_json_from)()
        self.assertEqual(response, {"hello": "session"})

        async_to_sync(communicator.disconnect)()
