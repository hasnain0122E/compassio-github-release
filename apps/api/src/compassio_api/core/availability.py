"""C11 policy v1: bounded, atomic token buckets for a single worker process.

Only the ASGI peer address is used. Run uvicorn with --no-proxy-headers unless a
separately reviewed trusted-proxy configuration guarantees that peer's provenance.
"""

import ipaddress
import math
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from compassio_api.core.middleware import ASGIApp, Receive, Scope, Send, _error


@dataclass(frozen=True)
class Budget:
    rate: float
    burst: float
    cost: float = 1

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) and x > 0 for x in (self.rate, self.burst, self.cost)):
            raise ValueError("C11 budgets must be positive finite numbers")
        if self.cost > self.burst:
            raise ValueError("C11 cost exceeds burst")


@dataclass
class Bucket:
    tokens: float
    updated: float


class Admission:
    """Atomic peer + global admission. Capacity pressure rejects new keys, never resets debt."""

    def __init__(
        self,
        policies: dict[str, tuple[Budget, Budget]],
        max_keys: int = 1024,
        idle_seconds: float = 120,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not policies or max_keys < len(policies) or not math.isfinite(idle_seconds):
            raise ValueError("Invalid C11 state configuration")
        if idle_seconds < max(peer.burst / peer.rate for peer, _ in policies.values()):
            raise ValueError("C11 expiry must allow complete peer refill")
        self.policies = dict(policies)
        self.max_keys = max_keys
        self.idle_seconds = idle_seconds
        self.clock = clock
        self.lock = threading.Lock()
        self.peers: OrderedDict[tuple[str, str], Bucket] = OrderedDict()
        self.globals: dict[str, Bucket] = {}
        self.admitted = 0
        self.rejected = 0
        self.evicted = 0
        self.high_water = 0
        self.key_counts = dict.fromkeys(policies, 0)

    def _prune(self, now: float) -> None:
        while self.peers:
            key, bucket = next(iter(self.peers.items()))
            if now - bucket.updated < self.idle_seconds:
                break
            del self.peers[key]
            self.key_counts[key[0]] -= 1
            self.evicted += 1

    @staticmethod
    def _tokens(bucket: Bucket, budget: Budget, now: float) -> float:
        return min(budget.burst, bucket.tokens + max(0, now - bucket.updated) * budget.rate)

    def admit(self, identity: str, route: str) -> int:
        """Return 0 on admission, otherwise an integer Retry-After in seconds. Never await."""
        with self.lock:
            now = self.clock()
            self._prune(now)
            peer_budget, global_budget = self.policies[route]
            key = (route, identity)
            peer = self.peers.get(key)
            global_bucket = self.globals.setdefault(route, Bucket(global_budget.burst, now))
            global_tokens = self._tokens(global_bucket, global_budget, now)
            if peer is None and self.key_counts[route] >= self.max_keys // len(self.policies):
                self.rejected += 1
                oldest = next(b for (kind, _), b in self.peers.items() if kind == route)
                return max(1, math.ceil(self.idle_seconds - (now - oldest.updated)))
            if peer is None:
                peer = Bucket(peer_budget.burst, now)
            tokens = self._tokens(peer, peer_budget, now)
            wait = max(
                (peer_budget.cost - tokens) / peer_budget.rate,
                (global_budget.cost - global_tokens) / global_budget.rate,
            )
            if wait > 0:
                self.rejected += 1
                return max(1, math.ceil(wait))
            if key not in self.peers:
                self.key_counts[route] += 1
            self.peers[key] = Bucket(tokens - peer_budget.cost, now)
            self.peers.move_to_end(key)
            self.globals[route] = Bucket(global_tokens - global_budget.cost, now)
            self.admitted += 1
            self.high_water = max(self.high_water, len(self.peers))
            return 0

    def snapshot(self) -> dict[str, int]:
        """Local instrumentation only; does not expose client identifiers over HTTP."""
        with self.lock:
            self._prune(self.clock())
            return {
                "keys": len(self.peers),
                "max_keys": self.max_keys,
                "high_water": self.high_water,
                "evicted": self.evicted,
                "admitted": self.admitted,
                "rejected": self.rejected,
            }


class AvailabilityShield:
    def __init__(self, app: ASGIApp, limiter: Admission) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or scope.get("method") == "OPTIONS"
            or not path.startswith("/api/v1/")
        ):
            await self.app(scope, receive, send)
            return
        route = (
            "screen"
            if path.startswith("/api/v1/screening/")
            or path.startswith("/api/v1/challenges/c09/")
            or (scope.get("method") == "POST" and path.startswith("/api/v1/decision/"))
            else "read"
        )
        client = scope.get("client")
        try:
            identity = str(ipaddress.ip_address(client[0])) if client else "unknown"
        except ValueError:
            identity = "unknown"
        retry = self.limiter.admit(identity, route)
        if retry:
            await _error(
                send,
                429,
                "rate_limited",
                "Too many requests. Please try again in a moment.",
                ((b"retry-after", str(retry).encode()),),
            )
            return
        await self.app(scope, receive, send)
