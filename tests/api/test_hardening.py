"""Task 009 request hardening: body limits, unknown fields, rate limiting, error hygiene,
security headers and lifecycle (artificial database)."""

import json
import logging
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compassio_api.core.config import Settings
from compassio_api.main import create_app

from .conftest import make_client

REPO = Path(__file__).resolve().parents[2]


def test_declared_oversized_body_is_rejected_before_parsing(seeded_url: str) -> None:
    client = make_client(seeded_url, max_request_body_bytes=2_048)
    body = json.dumps({"project_ids": ["aiddata:1", "aiddata:2"], "pad": "x" * 4_000})
    r = client.post(
        "/api/v1/decision/compare", content=body, headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413 and r.json()["code"] == "request_too_large"


def test_chunked_oversized_body_is_rejected(seeded_url: str) -> None:
    client = make_client(seeded_url, max_request_body_bytes=2_048)

    def chunks() -> Iterator[bytes]:
        yield b'{"project_ids": ["aiddata:1", "aiddata:2"], "pad": "'
        for _ in range(10):
            yield b"x" * 500
        yield b'"}'

    r = client.post(
        "/api/v1/decision/compare", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413 and r.json()["code"] == "request_too_large"


def test_chunked_body_within_the_limit_is_replayed_intact(seeded_url: str) -> None:
    client = make_client(seeded_url)

    def chunks() -> Iterator[bytes]:
        yield b'{"project_ids": ["aiddata:1",'
        yield b' "aiddata:2"]}'

    r = client.post(
        "/api/v1/decision/compare", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 200, r.text
    assert [p["project_id"] for p in r.json()["projects"]] == ["aiddata:1", "aiddata:2"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/decision/compare", {"project_ids": ["aiddata:1", "aiddata:2"], "x": 1}),
        ("/api/v1/decision/prioritize", {"filters": {"country": "PAK"}, "unexpected": True}),
        ("/api/v1/screening/text", {"title": "example_text", "unexpected": True}),
    ],
)
def test_unknown_request_fields_are_rejected(
    seeded_url: str, path: str, body: dict[str, Any]
) -> None:
    r = make_client(seeded_url).post(path, json=body)
    assert r.status_code == 422


def test_screening_requests_are_rate_limited_per_client(seeded_url: str) -> None:
    # Public mode: screening itself is refused (403), which still counts against the limit.
    client = make_client(seeded_url, source_data_access="public", screening_rate_limit_per_minute=2)
    codes = [
        client.post("/api/v1/screening/text", json={"title": "example_text"}).status_code
        for _ in range(3)
    ]
    assert codes == [403, 403, 429]
    r = client.post("/api/v1/screening/text", json={"title": "example_text"})
    assert r.json()["code"] == "rate_limited" and int(r.headers["Retry-After"]) >= 1
    # Other routes are not limited; another client has its own window.
    assert client.get("/api/v1/sources").status_code == 200
    other = TestClient(client.app, client=("127.0.0.2", 1))
    assert other.post("/api/v1/screening/text", json={"title": "example_text"}).status_code == 403


def test_rate_limit_can_be_disabled(seeded_url: str) -> None:
    client = make_client(seeded_url, source_data_access="public", screening_rate_limit_per_minute=0)
    for _ in range(5):
        assert client.post("/api/v1/screening/text", json={"title": "x"}).status_code == 403


def test_unhandled_errors_return_json_without_details(
    seeded_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(Settings(_env_file=None, database_url=seeded_url))

    @app.get("/example_boom")
    def boom() -> None:
        raise RuntimeError("example_secret_value in a stack frame")

    client = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="compassio_api"):
        r = client.get("/example_boom")
    assert r.status_code == 500
    assert r.json() == {"code": "internal_error", "message": "Internal server error."}
    assert "example_secret_value" not in r.text and "Traceback" not in r.text
    assert "example_secret_value" not in caplog.text  # only the exception type is logged


def test_security_headers(seeded_url: str) -> None:
    client = make_client(seeded_url)
    api = client.get("/api/v1/sources")
    assert api.headers["X-Content-Type-Options"] == "nosniff"
    assert api.headers["Referrer-Policy"] == "no-referrer"
    assert api.headers["Cache-Control"] == "no-store"
    assert client.get("/health").headers["X-Content-Type-Options"] == "nosniff"


def test_body_limit_and_rate_limit_settings_are_validated() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, max_request_body_bytes=10)
    with pytest.raises(ValueError):
        Settings(_env_file=None, screening_rate_limit_per_minute=-1)


def test_lifespan_preload_reports_missing_artifacts_without_crashing(
    seeded_url: str, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Preload verifies pinned models at startup; a missing artifact is logged (no stack
    trace, no secret) and the data API still starts. Artificial root: no model files."""
    (tmp_path / "configs").mkdir()
    for name in ("inference_models.yaml", "trusted_model_releases.json"):
        shutil.copy(REPO / "configs" / name, tmp_path / "configs" / name)
    app = create_app(
        Settings(
            _env_file=None,
            database_url=seeded_url,
            source_data_access="local_development",
            preload_models=True,
            inference_root=str(tmp_path),
        )
    )
    with caplog.at_level(logging.ERROR, logger="compassio_api"), TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/projects").status_code == 200
        assert app.state.model_manager is not None
    assert "model ml_v1 unavailable at startup" in caplog.text


def test_preload_is_skipped_when_inference_is_not_authorized(seeded_url: str) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=seeded_url,
            source_data_access="public",
            preload_models=True,
        )
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert getattr(app.state, "model_manager", None) is None


def test_validation_errors_use_the_common_envelope_without_echoing_input(seeded_url: str) -> None:
    secret = "example_confidential_project_text"
    r = make_client(seeded_url).post("/api/v1/screening/text", json={"title": secret, "top_k": 999})
    body = r.json()
    assert r.status_code == 422 and body["code"] == "invalid_request"
    assert body["message"].startswith("body.top_k")
    assert body["detail"][0]["loc"] == ["body", "top_k"]
    assert secret not in r.text


def test_early_rejections_carry_cors_headers_and_preflights_are_not_rate_limited(
    seeded_url: str,
) -> None:
    """Promotion-audit regression: CORS must be the outermost middleware so the browser
    frontend can read 413/429 bodies, and preflights must not consume screening slots."""
    origin = {"Origin": "http://localhost:3000"}
    client = make_client(
        seeded_url,
        source_data_access="public",
        screening_rate_limit_per_minute=2,
        max_request_body_bytes=2_048,
    )
    big = client.post(
        "/api/v1/screening/text",
        content=b"x" * 5_000,
        headers={**origin, "Content-Type": "application/json"},
    )
    assert big.status_code == 413
    assert big.headers["access-control-allow-origin"] == "http://localhost:3000"
    preflight = {
        **origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    for _ in range(5):
        assert client.options("/api/v1/screening/text", headers=preflight).status_code == 200
    codes = [
        client.post("/api/v1/screening/text", json={"title": "x"}, headers=origin) for _ in range(3)
    ]
    assert [r.status_code for r in codes] == [403, 403, 429]
    assert codes[2].headers["access-control-allow-origin"] == "http://localhost:3000"
    assert codes[2].headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("c11_enabled", [False, True])
def test_event_guard_rejection_carries_cors_headers(
    seeded_url: str, tmp_path: Path, c11_enabled: bool
) -> None:
    import yaml

    path = tmp_path / "example_event.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "authorizations": {
                    "example_event": {
                        "event": "example_event",
                        "granted_by": "example_organizer",
                        "reported_scope": "example scope",
                        "evidence_status": "user_reported_verbal_confirmation",
                        "recorded_on": "2026-01-01",
                        "permitted_uses": ["local_demonstration_to_judges_and_mentors"],
                        "excluded_uses": [
                            "public_deployment",
                            "redistribution_of_records_or_files",
                        ],
                        "sources": ["aiddata"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    app = create_app(
        Settings(
            _env_file=None,
            database_url=seeded_url,
            source_data_access="hackathon_event",
            event_authorization="example_event",
            event_authorizations_path=str(path),
            c11_enabled=c11_enabled,
        )
    )
    r = TestClient(app, client=("203.0.113.7", 1)).get(
        "/api/v1/projects", headers={"Origin": "http://localhost:3000"}
    )
    assert r.status_code == 403 and r.json()["code"] == "event_access_local_only"
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
