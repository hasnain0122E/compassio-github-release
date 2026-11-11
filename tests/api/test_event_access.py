"""Task 009 hackathon event access policy (artificial database and artificial authorization
files; the committed configs/event_data_authorizations.yaml is checked separately)."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db.session import create_read_engine
from compassio_api.main import create_app
from compassio_api.services.access import resolve_policy
from compassio_api.services.event_access import (
    EventAuthorization,
    EventConfigError,
    load_event_authorization,
)

REPO = Path(__file__).resolve().parents[2]
LOCAL = ("127.0.0.1", 50000)
REMOTE = ("203.0.113.7", 50000)  # TEST-NET-3 documentation address
DATA_ROUTES = (
    "/api/v1/projects",
    "/api/v1/projects/aiddata:1",
    "/api/v1/analytics/overview",
    "/api/v1/decision/evidence/aiddata:1",
)


def _entry(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "event": "example_event",
        "granted_by": "example_organizer",
        "reported_scope": "example scope",
        "evidence_status": "user_reported_verbal_confirmation",
        "evidence_reference": None,
        "recorded_on": "2026-01-01",
        "valid_from": None,
        "valid_until": None,
        "permitted_uses": ["local_demonstration_to_judges_and_mentors"],
        "excluded_uses": ["public_deployment", "redistribution_of_records_or_files"],
        "sources": ["aiddata", "gcf_projects", "gcf_historical"],
    }
    entry.update(overrides)
    return entry


def _file(tmp_path: Path, **overrides: Any) -> Path:
    path = tmp_path / "example_event_authorizations.yaml"
    doc = {"schema_version": 1, "authorizations": {"example_event": _entry(**overrides)}}
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    return path


def _client(url: str, path: Path, client: tuple[str, int] = LOCAL, **extra: Any) -> TestClient:
    values: dict[str, Any] = {
        "database_url": url,
        "source_data_access": "hackathon_event",
        "event_authorization": "example_event",
        "event_authorizations_path": str(path),
    }
    values.update(extra)
    return TestClient(create_app(Settings(_env_file=None, **values)), client=client)


# ------------------------------------------------------------------ configuration validation
def test_event_mode_requires_a_named_authorization() -> None:
    with pytest.raises(ValidationError, match="COMPASSIO_EVENT_AUTHORIZATION"):
        Settings(_env_file=None, source_data_access="hackathon_event")


def test_unknown_or_missing_authorization_stops_startup(seeded_url: str, tmp_path: Path) -> None:
    with pytest.raises(EventConfigError, match="unknown event authorization"):
        _client(seeded_url, _file(tmp_path), event_authorization="example_other")
    with pytest.raises(EventConfigError, match="not found"):
        _client(seeded_url, tmp_path / "example_missing.yaml")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"evidence_status": "written_evidence_on_file"}, "requires evidence_reference"),
        ({"excluded_uses": ["commercial_use"]}, "must exclude public_deployment"),
        ({"valid_from": "2026-02-01", "valid_until": "2026-01-01"}, "after valid_until"),
        ({"evidence_status": "licence_cleared"}, "evidence_status"),
        ({"sources": []}, "sources"),
    ],
)
def test_invalid_authorization_entries_are_rejected(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises(EventConfigError, match=message):
        load_event_authorization(_file(tmp_path, **overrides), "example_event")


def test_production_forces_public_even_in_event_mode(seeded_url: str, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        source_data_access="hackathon_event",
        event_authorization="example_event",
    )
    assert settings.effective_source_access == "public"
    assert not settings.inference_authorized and not settings.ml_v2_demo_active
    client = _client(seeded_url, _file(tmp_path), environment="production")
    for route in DATA_ROUTES:
        r = client.get(route)
        assert r.status_code == 403 and r.json()["code"] == "source_rights_not_cleared"
        assert r.headers["X-Compassio-Data-Access"] == "public"


# ------------------------------------------------------------------ authorized local use
def test_loopback_client_is_served_with_an_honest_event_notice(
    seeded_url: str, tmp_path: Path
) -> None:
    client = _client(seeded_url, _file(tmp_path))
    r = client.get("/api/v1/projects?page_size=50")
    assert r.status_code == 200
    assert r.headers["X-Compassio-Data-Access"] == "hackathon_event"
    body = r.json()
    assert body["access"]["mode"] == "hackathon_event"
    assert "not a licence clearance" in body["access"]["notice"]
    assert "user_reported_verbal_confirmation" in body["access"]["notice"]
    # Only the listed sources; restricted gcf_historical never, even though it is listed.
    assert {i["source_id"] for i in body["items"]} <= {"aiddata", "gcf_projects"}
    assert client.get("/api/v1/projects/aiddata:1").status_code == 200


def test_unlisted_and_restricted_sources_are_never_visible(seeded_url: str, tmp_path: Path) -> None:
    event = load_event_authorization(_file(tmp_path), "example_event")
    with Session(create_read_engine(seeded_url)) as session:
        policy = resolve_policy(session, "hackathon_event", event, date(2026, 6, 1))
        local = resolve_policy(session, "local_development")
    assert policy.visible_source_ids == {"aiddata", "gcf_projects"}
    assert "gcf_historical" not in local.visible_source_ids
    assert "climate_funds_update" in local.visible_source_ids  # event mode is narrower


def test_unlisted_source_record_is_not_found(seeded_url: str, tmp_path: Path) -> None:
    client = _client(seeded_url, _file(tmp_path, sources=["gcf_projects"]))
    assert client.get("/api/v1/projects/aiddata:1").status_code == 404


# ------------------------------------------------------------------ unauthorized use
def test_non_loopback_clients_are_refused(seeded_url: str, tmp_path: Path) -> None:
    client = _client(seeded_url, _file(tmp_path), client=REMOTE)
    for route in DATA_ROUTES:
        r = client.get(route)
        assert r.status_code == 403 and r.json()["code"] == "event_access_local_only"
    r = client.post("/api/v1/screening/text", json={"title": "example_text"})
    assert r.status_code == 403 and r.json()["code"] == "event_access_local_only"
    # Metadata without records stays available.
    assert client.get("/api/v1/sources").status_code == 200
    assert client.get("/api/v1/decision/methodology").status_code == 200
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "window",
    [
        {"valid_until": (date.today() - timedelta(days=1)).isoformat()},
        {"valid_from": (date.today() + timedelta(days=1)).isoformat()},
    ],
)
def test_outside_a_set_window_no_source_data_is_served(
    seeded_url: str, tmp_path: Path, window: dict[str, str]
) -> None:
    client = _client(seeded_url, _file(tmp_path, **window))
    for route in DATA_ROUTES:
        r = client.get(route)
        assert r.status_code == 403 and r.json()["code"] == "source_rights_not_cleared"


def test_unset_dates_mean_no_assumed_window() -> None:
    entry = EventAuthorization.model_validate(_entry())
    assert entry.active_on(date(2000, 1, 1)) and entry.active_on(date(2100, 1, 1))
    assert entry.window == "not set to not set"


def test_event_mode_allows_local_screening_but_v2_still_needs_its_flag() -> None:
    base: dict[str, Any] = {
        "source_data_access": "hackathon_event",
        "event_authorization": "example_event",
    }
    assert Settings(_env_file=None, **base).inference_authorized
    assert not Settings(_env_file=None, **base).ml_v2_demo_active
    assert Settings(_env_file=None, ml_v2_local_demo=True, **base).ml_v2_demo_active
    assert not Settings(
        _env_file=None, ml_v2_local_demo=True, environment="test", **base
    ).ml_v2_demo_active


# ------------------------------------------------------------------ committed configuration
def test_committed_event_authorization_is_recorded_honestly() -> None:
    entry = load_event_authorization(
        REPO / "configs" / "event_data_authorizations.yaml", "battleverse_2026"
    )
    assert entry.evidence_status == "user_reported_verbal_confirmation"
    assert entry.valid_from is None and entry.valid_until is None  # dates unknown, not assumed
    assert "gcf_historical" not in entry.sources
    for use in ("public_deployment", "commercial_use", "model_training"):
        assert use in entry.excluded_uses
