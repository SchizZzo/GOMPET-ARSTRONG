"""ASGI middleware helpers for authentication."""

from __future__ import annotations

import logging
from typing import Iterable, Tuple
from urllib.parse import parse_qs

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

logger = logging.getLogger(__name__)

Header = Tuple[bytes, bytes]


class JWTAuthMiddleware:
    """Authenticate websocket connections using JWT access tokens.

    The middleware checks the ``Authorization`` header for a bearer token and
    also supports a ``token`` query parameter for tooling that cannot easily set
    headers. When a valid token is found ``scope["user"]`` is populated with the
    authenticated user; otherwise the user remains unchanged.
    """

    def __init__(self, inner) -> None:
        self.inner = inner
        self.jwt_auth = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        token = self._get_token_from_scope(scope)

        if token is not None:
            try:
                validated_token = self.jwt_auth.get_validated_token(token)
                scope["user"] = self.jwt_auth.get_user(validated_token)
            except (InvalidToken, AuthenticationFailed) as exc:  # pragma: no cover - defensive
                logger.debug("JWT authentication failed during websocket handshake: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "Unexpected error during websocket JWT authentication: %s", exc, exc_info=True
                )

        return await self.inner(scope, receive, send)

    def _get_token_from_scope(self, scope: dict) -> str | None:
        headers: Iterable[Header] = scope.get("headers", [])
        raw_token = self._get_token_from_headers(headers)
        if raw_token:
            return raw_token

        return self._get_token_from_query(scope.get("query_string", b""))

    def _get_token_from_headers(self, headers: Iterable[Header]) -> str | None:
        for name, value in headers:
            if name.lower() == b"authorization":
                try:
                    prefix, token = value.decode().split(" ", 1)
                except ValueError:
                    return None

                if prefix.lower() == "bearer" and token:
                    return token
        return None

    def _get_token_from_query(self, query_string: bytes) -> str | None:
        if not query_string:
            return None

        params = parse_qs(query_string.decode())
        tokens = params.get("token")
        if tokens:
            return tokens[0]
        return None


def JWTAuthMiddlewareStack(inner):
    """Wrap the default auth stack with JWT authentication."""

    from channels.auth import AuthMiddlewareStack

    return JWTAuthMiddleware(AuthMiddlewareStack(inner))


__all__ = ["JWTAuthMiddleware", "JWTAuthMiddlewareStack"]
