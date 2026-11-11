"""LOCAL DATA: Task 008 decision engine on the REAL verified SQLite database (read-only).

Checks cross-endpoint consistency (insights vs the existing trends totals vs independent SQL on
the stored rows), double-counting rules on real records, determinism, and that the database
file is byte-for-byte unchanged afterwards. Skipped when the git-ignored database is absent.
"""

import hashlib
import sqlite3
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compassio_api.core.config import Settings
from compassio_api.main import create_app
from compassio_api.services.decision.evidence import MEANINGS

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "db" / "compassio_dev.sqlite"

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not DB.is_file(), reason="verified database absent"),
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def db_hash() -> Iterator[str]:
    before = _sha256(DB)
    yield before
    assert _sha256(DB) == before, "the verified database changed during the tests"


@pytest.fixture(scope="module")
def client(db_hash: str) -> TestClient:
    settings = Settings(
        _env_file=None,
        source_data_access="local_development",
        database_url=f"sqlite:///{DB.as_posix()}",
    )
    return TestClient(create_app(settings))


def _ro() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)


def _get(client: TestClient, path: str) -> dict[str, Any]:
    r = client.get(path)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


def test_every_stored_flow_kind_has_a_declared_meaning() -> None:
    with _ro() as con:
        kinds = {k for (k,) in con.execute("select distinct flow_kind from financial_observations")}
    assert kinds <= set(MEANINGS), kinds - set(MEANINGS)


@pytest.mark.parametrize(
    "metric",
    [
        "adb_disbursements_usd",
        "adb_commitments_usd",
        "aiddata_commitments_constant_2021_usd",
        "cfu_approvals_usd",
        "gcf_api_gcf_funding_by_country_usd",
    ],
)
def test_country_totals_equal_existing_trend_totals(client: TestClient, metric: str) -> None:
    profile = _get(client, "/api/v1/analytics/country-profile/PAK")
    summary = next(m for m in profile["metrics"] if m["declaration"]["metric_id"] == metric)
    trend = _get(client, f"/api/v1/analytics/trends?metric={metric}&country=PAK")
    trend_total = sum(Decimal(p["total"]) for p in trend["points"] if p["total"] is not None)
    assert Decimal(summary["all_years_total"]) == trend_total
    by_country = _get(client, f"/api/v1/analytics/funding-by-country?metric={metric}&limit=300")
    pak = next(g for g in by_country["groups"] if g["key"] == "PAK")
    assert Decimal(pak["total"]) == trend_total


def test_country_lines_split_world_total_without_double_counting(client: TestClient) -> None:
    metric = "gcf_api_gcf_funding_by_country_usd"
    groups = _get(client, f"/api/v1/analytics/funding-by-country?metric={metric}&limit=300")
    world = _get(client, f"/api/v1/analytics/trends?metric={metric}")
    split = sum(Decimal(g["total"]) for g in groups["groups"] if g["total"] is not None)
    assert groups["groups_total"] == groups["groups_shown"]
    assert split == sum(Decimal(p["total"]) for p in world["points"] if p["total"] is not None)


def test_adb_pakistan_total_matches_independent_sql(client: TestClient) -> None:
    with _ro() as con:
        rows = con.execute(
            "select amount from financial_observations where source_id='adb_pakistan' "
            "and flow_kind='disbursement' and value_status='reported'"
        ).fetchall()
    independent = sum((Decimal(a) for (a,) in rows), Decimal(0))
    body = _get(client, "/api/v1/analytics/funding-by-country?metric=adb_disbursements_usd")
    assert Decimal(body["groups"][0]["total"]) == independent
    assert body["declaration"]["is_funding"] is True
    repay = _get(client, "/api/v1/analytics/funding-by-country?metric=adb_principal_repayments_usd")
    assert repay["declaration"]["is_funding"] is False
    assert "NOT funding" in repay["declaration"]["financial_meaning"]


def test_real_same_package_pair_is_never_summed(client: TestClient) -> None:
    """Audit regression (Task 008 integration): AidData 35266 and 54087 sit in the same parent
    package. Both are recommended for aggregates, but the comparison must NOT present their
    sum as a user-facing total while it warns that they belong to the same package."""
    ids = ["gcf_projects:FP085", "aiddata:35266", "aiddata:54087"]
    body = client.post("/api/v1/decision/compare", json={"project_ids": ids}).json()
    warning = next(
        w for w in body["duplicate_warnings"] if w["relation_type"] == "same_source_record_group"
    )
    assert warning["project_ids"] == ["aiddata:35266", "aiddata:54087"]
    aid_groups = [g for g in body["comparable_groups"] if g["source_id"] == "aiddata"]
    assert aid_groups
    for g in aid_groups:
        assert g["selection_total"] is None and g["selection_total_status"] == "unavailable"
        assert "same source record group" in g["selection_total_reason"]
        # Each record's own source-reported figure is still shown.
        assert sum(1 for c in g["cells"] if c["facts"]) == 2
    gcf_groups = [g for g in body["comparable_groups"] if g["source_id"].startswith("gcf")]
    assert gcf_groups and all(g["selection_total"] is None for g in gcf_groups)


def test_real_cross_source_link_is_never_summed(client: TestClient) -> None:
    with _ro() as con:
        a, b = con.execute(
            "select from_project_id, to_project_id from project_relationships "
            "order by from_project_id limit 1"
        ).fetchone()
    body = client.post("/api/v1/decision/compare", json={"project_ids": [a, b]}).json()
    assert body["duplicate_warnings"][0]["project_ids"] == sorted([a, b])
    assert all(g["selection_total"] is None for g in body["comparable_groups"])


def test_real_multi_country_record_has_no_country_share(client: TestClient) -> None:
    with _ro() as con:
        (pid,) = con.execute(
            "select id from projects where source_id='gcf_projects' and multi_country=1 "
            "order by id limit 1"
        ).fetchone()
    ev = _get(client, f"/api/v1/decision/evidence/{pid}")["project"]
    assert ev["multi_country"] is True
    assert all(f["country_attribution"] != "single_country_project" for f in ev["headline_facts"])


def test_real_prioritization_is_reproducible(client: TestClient) -> None:
    body = {
        "filters": {"country": "PAK", "source": "climate_funds_update"},
        "sectors_of_interest": ["energy"],
        "page_size": 10,
    }
    first = client.post("/api/v1/decision/prioritize", json=body).json()
    other = TestClient(
        create_app(
            Settings(
                _env_file=None,
                source_data_access="local_development",
                database_url=f"sqlite:///{DB.as_posix()}",
            )
        )
    )
    second = other.post("/api/v1/decision/prioritize", json=body).json()
    assert first["items"] == second["items"] and first["candidates"] == 31
    assert first["ranking_fingerprint"] == second["ranking_fingerprint"]


def test_real_scenario_conserves_and_warns(client: TestClient) -> None:
    ids = [
        "climate_funds_update:projects-r2724",
        "climate_funds_update:projects-r2845",
        "climate_funds_update:projects-r2572",
    ]
    s = client.post(
        "/api/v1/decision/scenarios",
        json={
            "budget": {"amount": "2500000", "currency": "USD"},
            "project_ids": ids,
            "method": "priority_score",
            "constraints": {"max_per_project": "1000000"},
        },
    ).json()
    total = sum(Decimal(a["allocation"]) for a in s["allocations"]) + Decimal(s["unallocated"])
    assert total == Decimal(2_500_000)
    assert all(a["reference_facts"] for a in s["allocations"])
    assert all(any("not determinable" in w for w in a["warnings"]) for a in s["allocations"])
