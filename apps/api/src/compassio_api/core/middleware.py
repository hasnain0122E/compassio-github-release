"""Task 009 request hardening (pure ASGI, no third-party dependency).

* ``BodySizeLimit``: 413 ``request_too_large`` before any parsing, whether or not the client
  sends ``Content-Length``.
* ``EventLoopbackGuard``: in ``hackathon_event`` mode only loopback clients may use
  ``/api/v1`` (except metadata routes): 403 ``event_access_local_only``.
* ``ScreeningRateLimit``: per-client sliding one-minute window on ``/api/v1/screening/``:
  429 ``rate_limited`` with ``Retry-After``. In-process state: valid for ONE worker process
  (the supported deployment; see docs/hackathon/local_demo_runbook.md).
* ``SecurityHeaders``: ``nosniff``, ``no-referrer``, and ``no-store`` on API responses.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, MutableMapping
from contextlib import suppress
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
EVENT_PUBLIC_PATHS = frozenset({"/api/v1/meta", "/api/v1/sources", "/api/v1/decision/methodology"})


async def _error(
    send: Send, status: int, code: str, message: str, headers: tuple[tuple[bytes, bytes], ...] = ()
) -> None:
    body = json.dumps({"code": code, "message": message}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodySizeLimit:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, receive: Receive, send: Send, message: str) -> None:
        # Windows TCP can reset a response when the server closes with unread input.
        # Drain small demo uploads without buffering or parsing. Slow/huge senders have
        # a fixed time/byte budget; never turn rejection into unbounded work.
        async def drain() -> None:
            total = 0
            while total <= max(1_048_576, self.max_bytes * 4):
                part = await receive()
                total += len(part.get("body", b""))
                if part["type"] != "http.request" or not part.get("more_body", False):
                    return

        with suppress(TimeoutError):
            await asyncio.wait_for(drain(), timeout=1.0)
        await _error(send, 413, "request_too_large", message, ((b"connection", b"close"),))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        too_large = (
            f"Request body exceeds {self.max_bytes} bytes (COMPASSIO_MAX_REQUEST_BODY_BYTES)."
        )
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                await _error(send, 400, "invalid_content_length", "Invalid Content-Length.")
                return
            if size > self.max_bytes:
                await self._reject(receive, send, too_large)
                return
            await self.app(scope, receive, send)
            return
        if scope.get("method") not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        # No Content-Length (chunked): buffer up to the limit, then replay.
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                if message.get("more_body", False):
                    await self._reject(receive, send, too_large)
                else:
                    await _error(send, 413, "request_too_large", too_large)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        sent = False

        async def replay() -> Message:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def _client_host(scope: Scope) -> str:
    client = scope.get("client")
    return str(client[0]) if client else ""


class EventLoopbackGuard:
    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] == "http"
            and path.startswith(self.prefix)
            and path not in EVENT_PUBLIC_PATHS
            and _client_host(scope) not in LOOPBACK
        ):
            await _error(
                send,
                403,
                "event_access_local_only",
                "Event demonstration mode serves data only to clients on this machine "
                "(run the API with --host 127.0.0.1).",
            )
            return
        await self.app(scope, receive, send)


class ScreeningRateLimit:
    def __init__(
        self,
        app: ASGIApp,
        per_minute: int,
        prefix: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.per_minute = per_minute
        self.prefix = prefix
        self.clock = clock
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") != "OPTIONS"  # CORS preflights never count
            and (
                scope.get("path", "").startswith(self.prefix)
                or scope.get("path", "").startswith("/api/v1/challenges/c09/")
            )
        ):
            now = self.clock()
            window = self.hits[_client_host(scope)]
            while window and now - window[0] >= 60.0:
                window.popleft()
            if len(window) >= self.per_minute:
                retry = max(1, int(60.0 - (now - window[0])) + 1)
                await _error(
                    send,
                    429,
                    "rate_limited",
                    f"At most {self.per_minute} screening requests per minute per client "
                    "(COMPASSIO_SCREENING_RATE_LIMIT_PER_MINUTE).",
                    ((b"retry-after", str(retry).encode()),),
                )
                return
            window.append(now)
        await self.app(scope, receive, send)


class SecurityHeaders:
    def __init__(self, app: ASGIApp, api_prefix: str) -> None:
        self.app = app
        self.api_prefix = api_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = scope.get("path", "").startswith(self.api_prefix)

        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"referrer-policy", b"no-referrer"))
                if is_api:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrapped)
