"""Deterministic policy and real application integration; no performance CI thresholds."""

import asyncio
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from compassio_api.core.availability import Admission, AvailabilityShield, Budget
from compassio_api.core.config import Settings
from compassio_api.core.middleware import Message, Scope
from compassio_api.main import create_app

from .test_screening import TEXT, client, models_root  # noqa: F401 (pytest fixture)


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def limiter(clock: Clock, **kwargs: Any) -> Admission:
    return Admission({"screen": (Budget(2, 4), Budget(100, 100))}, clock=clock, **kwargs)


def test_refill_burst_boundary_retry_and_sustained_abuse() -> None:
    clock = Clock()
    gate = limiter(clock)
    assert [gate.admit("a", "screen") for _ in range(6)] == [0, 0, 0, 0, 1, 1]
    clock.now = 0.499
    assert gate.admit("a", "screen") == 1
    clock.now = 0.5
    assert gate.admit("a", "screen") == 0
    for i in range(1, 101):
        clock.now = 0.5 + i / 200
        assert (gate.admit("a", "screen") == 0) == (i == 100)
    assert gate.snapshot()["admitted"] == 6


def test_atomic_threaded_admission_and_independent_peers() -> None:
    clock = Clock()
    gate = limiter(clock)
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda _: gate.admit("a", "screen"), range(1000)))
    assert results.count(0) == 4
    assert gate.admit("other", "screen") == 0
    # A second device behind the same NAT gets the same exhausted bucket.
    assert gate.admit("a", "screen") == 1


def test_global_ceiling_no_identity_churn_and_cleanup() -> None:
    clock = Clock()
    gate = limiter(clock, max_keys=3, idle_seconds=2)
    for key in ("a", "b", "c"):
        assert gate.admit(key, "screen") == 0
    for i in range(10000):
        assert gate.admit(str(i), "screen") == 2
    assert gate.snapshot()["keys"] == 3
    clock.now = 2
    assert gate.snapshot()["keys"] == 0
    assert gate.snapshot()["evicted"] == 3
    assert gate.admit("new", "screen") == 0
    global_gate = Admission({"screen": (Budget(2, 4), Budget(1, 2))}, clock=clock)
    assert [global_gate.admit(str(i), "screen") for i in range(4)] == [0, 0, 1, 1]
    assert global_gate.snapshot()["keys"] == 2  # global rejection allocates no peer key


def test_cost_and_retry_ceiling() -> None:
    clock = Clock()
    gate = Admission({"screen": (Budget(0.25, 2, 2), Budget(1, 20))}, clock=clock)
    assert gate.admit("a", "screen") == 0
    assert gate.admit("a", "screen") == 8
    clock.now = 0.01
    assert gate.admit("a", "screen") == 8
    clock.now = 8
    assert gate.admit("a", "screen") == 0


def test_reserved_read_state_and_budget_under_identity_churn() -> None:
    clock = Clock()
    gate = Admission(
        {name: (Budget(1, 2), Budget(100, 100)) for name in ("screen", "read")},
        max_keys=4,
        clock=clock,
    )
    assert gate.admit("bot1", "screen") == 0
    assert gate.admit("bot2", "screen") == 0
    assert gate.admit("bot3", "screen") > 0
    assert gate.admit("normal", "read") == 0
    assert gate.snapshot()["keys"] == 3


def test_fixture_model_hashes_database_integrity_unchanged(
    models_root: Path,  # noqa: F811
    seeded_url: str,
) -> None:
    files = list(models_root.rglob("*.joblib"))
    files.append(Path(seeded_url.removeprefix("sqlite:///")))
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    c = client(models_root, seeded_url, c11_enabled=True, ml_v2_local_demo=True)
    for model in ("ml_v1", "ml_v2"):
        assert c.post("/api/v1/screening/text", json={**TEXT, "model": model}).status_code == 200
    assert c.get("/api/v1/projects").status_code == 200
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with sqlite3.connect(f"{files[-1].resolve().as_uri()}?mode=ro", uri=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "rate,burst,cost",
    [(0, 1, 1), (-1, 2, 1), (float("nan"), 2, 1), (1, float("inf"), 1), (1, 1, 2)],
)
def test_invalid_budget_fails_at_startup(rate: float, burst: float, cost: float) -> None:
    with pytest.raises(ValueError):
        Budget(rate, burst, cost)


def test_invalid_state_and_settings_fail_closed() -> None:
    for kwargs in ({"max_keys": 0}, {"idle_seconds": 1}, {"idle_seconds": float("inf")}):
        with pytest.raises(ValueError):
            limiter(Clock(), **kwargs)
    configurations: list[dict[str, Any]] = [
        {"c11_screen_rate": 0},
        {"c11_screen_rate": float("nan")},
        {"c11_idle_seconds": 1},
        {"c11_max_keys": 0},
        {"c11_enabled": "garbage"},
    ]
    for kwargs in configurations:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **kwargs)
    assert not Settings(_env_file=None).c11_enabled


def test_asgi_exemptions_nonblocking_and_forwarded_headers_ignored() -> None:
    async def exercise() -> None:
        calls: list[str] = []
        messages: list[Message] = []

        async def downstream(scope: Scope, receive: Any, send: Any) -> None:
            calls.append(scope["path"])

        async def receive() -> dict[str, Any]:
            raise AssertionError("Admission must not read request bodies")

        async def send(message: Message) -> None:
            messages.append(message)

        clock = Clock()
        gate = limiter(clock)
        shield = AvailabilityShield(downstream, gate)
        base = {
            "type": "http",
            "path": "/api/v1/screening/text",
            "method": "POST",
            "client": ("127.0.0.1", 1),
        }
        for _ in range(4):
            await shield(base, receive, send)
        for i in range(10):
            await shield(
                {**base, "headers": [(b"x-forwarded-for", str(i).encode())]}, receive, send
            )
        assert len(calls) == 4
        assert sum(m.get("status") == 429 for m in messages) == 10
        for scope in (
            {**base, "method": "OPTIONS"},
            {**base, "path": "/health"},
            {**base, "type": "websocket"},
        ):
            await shield(scope, receive, send)
        assert len(calls) == 7
        # No sleep/await in admission; downstream remains independently schedulable.
        marker = asyncio.Event()

        async def mark() -> None:
            marker.set()

        await asyncio.gather(mark(), shield(base, receive, send))
        assert marker.is_set()

    asyncio.run(exercise())


def test_c11_http_cors_preflight_size_and_early_model_rejection(seeded_url: str) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=seeded_url,
            c11_enabled=True,
            c11_screen_burst=1,
            c11_screen_rate=0.01,
            c11_idle_seconds=120,
            max_request_body_bytes=2048,
        )
    )
    c = TestClient(app)
    origin = {"Origin": "http://localhost:3000"}
    for _ in range(3):
        r = c.options(
            "/api/v1/screening/text", headers={**origin, "Access-Control-Request-Method": "POST"}
        )
        assert r.status_code == 200
    assert c.post("/api/v1/screening/text", content=b"x" * 3000).status_code == 413
    # Exhaust directly: rejecting HTTP traffic must never instantiate model manager or DB.
    assert app.state.c11_limiter.admit("testclient", "screen") == 0
    # testclient's invalid IP normalizes to the shared unknown identity.
    assert app.state.c11_limiter.admit("unknown", "screen") == 0
    r = c.post("/api/v1/screening/text", json=TEXT, headers=origin)
    assert r.status_code == 429
    assert r.json() == {
        "code": "rate_limited",
        "message": "Too many requests. Please try again in a moment.",
    }
    assert int(r.headers["retry-after"]) in (99, 100)
    assert r.headers["access-control-allow-origin"] == origin["Origin"]
    assert "Retry-After" in r.headers["access-control-expose-headers"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert getattr(app.state, "model_manager", None) is None
    assert c.get("/api/v1/meta").status_code == 200


def test_authorized_inference_guards_and_no_stacked_limit(models_root: Path) -> None:  # noqa: F811
    c = client(models_root, c11_enabled=True, screening_rate_limit_per_minute=1)
    assert [c.post("/api/v1/screening/text", json=TEXT).status_code for _ in range(3)] == [200] * 3
    public = client(models_root, c11_enabled=True, environment="production")
    assert public.post("/api/v1/screening/text", json=TEXT).status_code == 403
    local = client(models_root, c11_enabled=True)
    assert local.post("/api/v1/screening/text", json={**TEXT, "model": "ml_v2"}).status_code == 403
    assert local.post("/api/v1/screening/text", json={**TEXT, "save": True}).status_code == 403
