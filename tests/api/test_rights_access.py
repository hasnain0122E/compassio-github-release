"""Source-rights access guard (artificial database; rights evidence strings are fixtures)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from compassio_api.core.config import Settings

from .conftest import make_client, seed

DATA_ROUTES = (
    "/api/v1/projects",
    "/api/v1/projects/aiddata:1",
    "/api/v1/filters",
    "/api/v1/analytics/overview",
    "/api/v1/analytics/metrics",
    "/api/v1/analytics/trends?metric=cfu_approvals_usd",
)


def test_public_exposure_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMPASSIO_SOURCE_DATA_ACCESS", raising=False)

    assert Settings(_env_file=None).source_data_access == "public"


@pytest.mark.parametrize(
    "settings",
    [
        {"source_data_access": "public"},
        {"environment": "production", "source_data_access": "local_development"},
    ],
)
@pytest.mark.parametrize("route", DATA_ROUTES)
def test_data_routes_fail_closed_without_cleared_sources(
    seeded_url: str, settings: dict[str, Any], route: str
) -> None:
    client = make_client(seeded_url, **settings)

    response = client.get(route)

    assert response.status_code == 403
    assert response.json()["code"] == "source_rights_not_cleared"
    assert response.headers["X-Compassio-Data-Access"] == "public"


def test_production_ignores_local_development_setting() -> None:
    settings = Settings(
        _env_file=None, environment="production", source_data_access="local_development"
    )

    assert settings.effective_source_access == "public"


def test_sources_metadata_stays_available_and_reports_rights(seeded_url: str) -> None:
    client = make_client(seeded_url, environment="production")

    body = client.get("/api/v1/sources").json()

    assert body["access"]["mode"] == "public"
    assert not any(s["served_in_current_mode"] for s in body["sources"])


@pytest.fixture
def gcf_only_client(db_url: str, write_engine: Engine) -> TestClient:
    seed(
        write_engine,
        rights={"gcf_projects": ("permitted", "example evidence: fixture only, not a review")},
    )
    return make_client(db_url, source_data_access="public")


def test_public_mode_serves_only_evidenced_sources(gcf_only_client: TestClient) -> None:
    body = gcf_only_client.get("/api/v1/projects?page_size=100").json()

    assert {i["source_id"] for i in body["items"]} == {"gcf_projects"}
    assert gcf_only_client.get("/api/v1/projects/aiddata:1").status_code == 404
    assert gcf_only_client.get("/api/v1/projects?source=aiddata").json()["items"] == []


def test_public_mode_hides_links_to_uncleared_sources(gcf_only_client: TestClient) -> None:
    detail = gcf_only_client.get("/api/v1/projects/gcf_projects:FP901").json()

    assert detail["relationships"] == []  # the linked CFU row's source is not cleared


def test_public_mode_blocks_metrics_from_uncleared_sources(gcf_only_client: TestClient) -> None:
    blocked = gcf_only_client.get("/api/v1/analytics/trends?metric=cfu_approvals_usd")
    metrics = gcf_only_client.get("/api/v1/analytics/metrics").json()["metrics"]

    assert blocked.status_code == 403
    assert {m["source_id"] for m in metrics} == {"gcf_projects"}


def test_annotations_need_their_own_source_cleared(db_url: str, write_engine: Engine) -> None:
    seed(write_engine, rights={"aiddata": ("permitted", "example evidence: fixture only")})
    client = make_client(db_url, source_data_access="public")

    detail = client.get("/api/v1/projects/aiddata:1").json()

    assert detail["climate_annotations"] == []  # research_paper is not cleared
    assert client.get("/api/v1/projects?climate_related=true").json()["items"] == []
