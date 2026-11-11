"""LOCAL DATA: Task 006-DB sources on the real files + the registered GCF API snapshot.

Skipped when the raw files, the research table or a registered backend snapshot are absent.
Coverage numbers are asserted only where an audit document fixes them; enrichment coverage is
checked for consistency (e.g. matched <= export rows), never against a hard-coded target.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db.migrate import upgrade
from compassio_api.db.session import create_write_engine
from compassio_api.ingest.runner import ALL_ORDER, ingest
from compassio_api.main import create_app
from compassio_api.services.integrity import verify_database
from compassio_api.services.reports import gcf_enrichment_report, reconciliation_report
from compassio_api.staging.registry import load_registry, validate_registry
from compassio_ml.data.layout import DataLayout

REPO = Path(__file__).resolve().parents[1]
LAYOUT = DataLayout(REPO / "data")
HAS_DATA = (LAYOUT.raw / "gcf_projects").is_dir() and (
    LAYOUT.processed / "research_projects.parquet"
).is_file()
HAS_SNAPSHOT = load_registry(LAYOUT.root).latest("gcf_api_projects") is not None

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not (HAS_DATA and HAS_SNAPSHOT), reason="local data or snapshot absent"),
]


@pytest.fixture(scope="module")
def real_db(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Engine, dict[str, Any]]]:
    url = f"sqlite:///{(tmp_path_factory.mktemp('realdb2') / 'compassio.sqlite').as_posix()}"
    upgrade(url)
    engine = create_write_engine(url)
    report = ingest(engine, LAYOUT, list(ALL_ORDER), REPO)
    yield url, engine, report
    engine.dispose()


def _client(url: str, **settings: Any) -> TestClient:
    values: dict[str, Any] = {"database_url": url, "source_data_access": "local_development"}
    values.update(settings)
    return TestClient(create_app(Settings(_env_file=None, **values)))


def test_backend_registry_is_valid() -> None:
    report = validate_registry(LAYOUT.root)

    assert report.ok, report.errors


def test_all_audited_figures_match(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    with Session(real_db[1]) as session:
        report = verify_database(session)

    assert {k: v for k, v in report["audited_comparisons"].items() if not v["match"]} == {}
    assert report["structural_checks"]["ok"] is True
    assert report["structural_checks"]["restricted_internal_sources"] == ["gcf_historical"]


def test_enrichment_coverage_is_consistent(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    with Session(real_db[1]) as session:
        report = gcf_enrichment_report(session)

    assert report["export_projects"] == 379
    assert report["matched_export_projects"] <= report["export_projects"]
    assert (
        report["matched_export_projects"] + len(report["export_projects_without_api_record"]) == 379
    )
    assert report["with_verified_approval_date"] <= report["matched_export_projects"]
    assert report["pakistan"]["export_projects_listing_pakistan"] == 11


def test_no_double_counting(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    with Session(real_db[1]) as session:
        report = reconciliation_report(session)

    assert all(v == 0 for v in report["checks"].values()), report["checks"]
    assert report["project_rows_by_source"]["gcf_projects"] == 379


def test_reingestion_of_new_sources_writes_nothing(
    real_db: tuple[str, Engine, dict[str, Any]],
) -> None:
    keys = [
        "gcf_readiness",
        "gcf_countries",
        "climate_project_explorer",
        "gcf_historical",
        "gcf_api_projects",
    ]
    report = ingest(real_db[1], LAYOUT, keys, REPO)["sources"]

    assert report["gcf_readiness"]["inserted"] == report["gcf_readiness"]["updated"] == 0
    for key, block in (
        ("gcf_countries", "country_aggregates"),
        ("climate_project_explorer", "documents"),
        ("gcf_historical", "historical_staging"),
        ("gcf_api_projects", "enrichments"),
    ):
        counts = report[key][block]
        assert counts["inserted"] == counts["updated"] == counts["removed"] == 0, key
    api_obs = report["gcf_api_projects"]["observations"]
    assert api_obs["inserted"] == api_obs["updated"] == api_obs["removed"] == 0


def test_fts_search_matches_plain_scan_on_real_data(
    real_db: tuple[str, Engine, dict[str, Any]],
) -> None:
    url = real_db[0]
    client = _client(url)
    path = url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        for q in ("hydropower", "climate resilience", "flood", "Karachi"):
            pattern = f"%{q}%"
            expected = con.execute(
                "select count(*) from projects where title like ? escape '\\' "
                "or description like ? escape '\\'",
                (pattern, pattern),
            ).fetchone()[0]
            body = client.get("/api/v1/projects", params={"q": q, "page_size": 1}).json()
            assert body["pagination"]["total_items"] == expected, q


def test_real_pakistan_gcf_timeline_and_rights(
    real_db: tuple[str, Engine, dict[str, Any]],
) -> None:
    client = _client(real_db[0])
    body = client.get("/api/v1/analytics/gcf-timeline?country=PAK").json()

    assert sum(p["projects_approved"] for p in body["points"]) <= 11
    assert all(
        p["gcf_funding"] is None or p["gcf_funding"]["unit"] == "USD" for p in body["points"]
    )
    production = _client(real_db[0], environment="production")
    assert production.get("/api/v1/analytics/gcf-timeline").status_code == 403
