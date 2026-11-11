"""LOCAL DATA: ingest the real registered sources into a temporary database and verify them.

Skipped when the raw files or the Task 003 research table are absent. Expected values are the
committed audit figures (see compassio_api.services.integrity.EXPECTED), not tuned here.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db.migrate import upgrade
from compassio_api.db.models import FinancialObservation, Project
from compassio_api.db.session import create_write_engine
from compassio_api.ingest.runner import ORDER, ingest
from compassio_api.main import create_app
from compassio_api.services.integrity import verify_database
from compassio_ml.data.layout import DataLayout

REPO = Path(__file__).resolve().parents[1]
LAYOUT = DataLayout(REPO / "data")
NEEDED = (
    LAYOUT.raw / "research_paper",
    LAYOUT.raw / "gcf_projects",
    LAYOUT.processed / "research_projects.parquet",
)

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not all(p.exists() for p in NEEDED), reason="local source data absent"),
]


@pytest.fixture(scope="module")
def real_db(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[str, Engine, dict[str, Any]]]:
    url = f"sqlite:///{(tmp_path_factory.mktemp('realdb') / 'compassio.sqlite').as_posix()}"
    upgrade(url)
    engine = create_write_engine(url)
    first = ingest(engine, LAYOUT, list(ORDER), REPO)
    yield url, engine, first
    engine.dispose()


def _client(url: str, **settings: Any) -> TestClient:
    values: dict[str, Any] = {"database_url": url, "source_data_access": "local_development"}
    values.update(settings)
    return TestClient(create_app(Settings(_env_file=None, **values)))


def test_first_ingestion_imports_every_record(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    _, _, report = real_db
    inserted = {k: v["inserted"] for k, v in report["sources"].items()}

    assert inserted == {
        "research_paper": 20_985,
        "gcf_projects": 379,
        "climate_funds_update": 4_066,
        "adb_pakistan": 193,
    }
    assert all(v["rejected"] == 0 for v in report["sources"].values())
    assert report["links"]["cfu_to_gcf_links"] == 329


def test_database_matches_audited_source_facts(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    _, engine, _ = real_db
    with Session(engine) as session:
        report = verify_database(session)

    mismatches = {k: v for k, v in report["audited_comparisons"].items() if not v["match"]}
    assert mismatches == {}
    assert report["structural_checks"]["ok"] is True
    assert report["structural_checks"]["sources_cleared_for_public_display"] == []


def test_reingestion_adds_nothing(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    _, engine, _ = real_db
    with Session(engine) as session:
        before = session.scalar(select(func.count()).select_from(FinancialObservation))

    report = ingest(engine, LAYOUT, list(ORDER), REPO)

    for result in report["sources"].values():
        assert (result["inserted"], result["updated"], result["removed"]) == (0, 0, 0)
    with Session(engine) as session:
        after = session.scalar(select(func.count()).select_from(FinancialObservation))
        projects = session.scalar(select(func.count()).select_from(Project))
    assert before == after
    assert projects == 20_985 + 379 + 4_066 + 193


def test_real_pakistan_queries(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    client = _client(real_db[0])

    pk = client.get("/api/v1/projects?source=aiddata&country=PAK&page_size=1").json()
    pk_climate = client.get(
        "/api/v1/projects?source=aiddata&country=PAK&climate_related=true&page_size=1"
    ).json()
    gcf_pk = client.get("/api/v1/projects?source=gcf_projects&country=PAK&page_size=100").json()

    assert pk["pagination"]["total_items"] == 496
    assert pk_climate["pagination"]["total_items"] == 76
    assert gcf_pk["pagination"]["total_items"] == 11
    assert sum(1 for i in gcf_pk["items"] if i["multi_country"]) == 3


def test_real_detail_search_and_links(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    client = _client(real_db[0])

    detail = client.get("/api/v1/projects/gcf_projects:FP085").json()
    search = client.get("/api/v1/projects?q=hydropower&country=PAK").json()

    assert detail["title"] == "Green BRT Karachi"
    assert [c["iso3"] for c in detail["countries"]] == ["PAK"]
    assert detail["financial_observations"][0]["currency"] is None  # not stated by GCF
    assert any(r["other_source_id"] == "climate_funds_update" for r in detail["relationships"])
    assert search["pagination"]["total_items"] > 0
    assert all("PAK" in [c["iso3"] for c in i["countries"]] for i in search["items"])


def test_real_trend_is_single_source_and_labelled(
    real_db: tuple[str, Engine, dict[str, Any]],
) -> None:
    client = _client(real_db[0])

    body = client.get(
        "/api/v1/analytics/trends?metric=aiddata_commitments_constant_2021_usd&country=PAK"
    ).json()

    assert body["status"] == "available"
    assert body["metric"]["price_basis"] == "constant_2021_usd"
    assert {p["year"] for p in body["points"]} <= set(range(2000, 2022))
    assert all(p["total"] is None or isinstance(p["total"], str) for p in body["points"])


def test_real_data_not_exposed_publicly(real_db: tuple[str, Engine, dict[str, Any]]) -> None:
    client = _client(real_db[0], environment="production")

    response = client.get("/api/v1/projects")

    assert response.status_code == 403
    assert response.json()["code"] == "source_rights_not_cleared"
