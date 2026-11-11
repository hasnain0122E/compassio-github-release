"""Task 006-DB routes and rights on an ARTIFICIAL database (numbers are test inputs)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from .conftest import make_client, seed_extended


@pytest.fixture
def client(extended_url: str) -> TestClient:
    return make_client(extended_url)


def test_detail_shows_enrichment_documents_and_country_lines(client: TestClient) -> None:
    detail = client.get("/api/v1/projects/gcf_projects:FP902").json()

    enrichment = detail["enrichments"][0]
    assert enrichment["approval_date"] == "2017-05-05"
    assert enrichment["status_as_of_meaning"].startswith("The API publishes no as-of date")
    assert [c["field"] for c in enrichment["conflicts"]] == ["title"]
    assert detail["title"] == "example_gcf_multi"  # export value kept
    zzb = [
        o
        for o in detail["financial_observations"]
        if o["observation_key"].startswith("FP902:country:ZZB")
    ]
    assert {o["currency"] for o in zzb} == {"USD"}
    assert [d["verification_state"] for d in detail["documents"]] == ["candidate_requires_review"]


def test_country_breakdown_metric_uses_the_published_country_share(client: TestClient) -> None:
    all_points = {
        p["year"]: p
        for p in client.get(
            "/api/v1/analytics/trends?metric=gcf_api_gcf_funding_by_country_usd"
        ).json()["points"]
    }
    zzb = client.get(
        "/api/v1/analytics/trends?metric=gcf_api_gcf_funding_by_country_usd&country=ZZB"
    ).json()["points"]

    assert all_points[2016]["total"] == "1000" and all_points[2017]["total"] == "2000"
    assert [(p["year"], p["total"]) for p in zzb] == [(2017, "800")]  # never the whole 2000


def test_instrument_line_metric_excludes_inconsistent_and_eur_lines(client: TestClient) -> None:
    points = {
        p["year"]: p
        for p in client.get("/api/v1/analytics/trends?metric=gcf_api_gcf_funding_usd").json()[
            "points"
        ]
    }

    assert points[2016]["total"] == "1000"
    assert points[2017]["status"] == "unavailable"
    assert points[2017]["excluded_records"] == {
        "funding_lines_inconsistent_with_published_total": 1
    }


def test_gcf_timeline_and_meta(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/gcf-timeline").json()

    assert [(p["year"], p["projects_approved"]) for p in body["points"]] == [(2016, 1), (2017, 1)]
    assert body["projects_meta"]["unit_of_observation"] == "one GCF funded project (FP/SAP)"
    assert body["funding_meta"]["currency"] == "USD"
    assert body["funding_meta"]["deduplication_policy"]


def test_documents_endpoint(client: TestClient) -> None:
    linked = client.get("/api/v1/documents?project_id=gcf_projects:FP901").json()
    gef = client.get("/api/v1/documents?fund=GEF").json()

    assert linked["pagination"]["total_items"] == 2
    assert all("does not store or redistribute" in d["rights_notice"] for d in linked["items"])
    assert gef["items"][0]["linked_project_ids"] == []
    assert client.get("/api/v1/documents?fund=gef").status_code == 422


def test_country_aggregates_endpoint_states_the_rule(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/country-aggregates?iso3=ZZA").json()

    assert len(body["items"]) == 4
    assert "never add them to project-level observations" in body["rule"]
    assert all(i["meta"]["deduplication_policy"] for i in body["items"])


def test_quality_completeness_and_relationships(client: TestClient) -> None:
    quality = {
        s["source_id"]: s for s in client.get("/api/v1/analytics/data-quality").json()["sources"]
    }
    flows = client.get("/api/v1/analytics/financing-completeness").json()["flows"]
    rels = client.get("/api/v1/analytics/relationships").json()

    assert quality["gcf_readiness"]["rows"] == 4
    gcf = next(f for f in flows if f["source_id"] == "gcf_projects")
    assert gcf["reported_without_currency"] == gcf["reported"]  # export currency not stated
    tables = {r["table"] for r in rels["rows"]}
    assert tables == {
        "project_relationships",
        "document_links",
        "project_enrichments",
        "record_groups",
    }
    assert any("not probabilities" in p for p in rels["policy"])


def test_historical_staging_is_not_reachable(client: TestClient) -> None:
    sources = {s["source_id"]: s for s in client.get("/api/v1/sources").json()["sources"]}

    assert sources["gcf_historical"]["served_in_current_mode"] is False
    assert client.get("/api/v1/projects?source=gcf_historical").json()["items"] == []


@pytest.mark.parametrize(
    "route",
    [
        "/api/v1/documents",
        "/api/v1/analytics/data-quality",
        "/api/v1/analytics/financing-completeness",
        "/api/v1/analytics/gcf-timeline",
        "/api/v1/analytics/country-aggregates",
        "/api/v1/analytics/relationships",
    ],
)
def test_new_routes_fail_closed_in_production(extended_url: str, route: str) -> None:
    response = make_client(extended_url, environment="production").get(route)

    assert response.status_code == 403
    assert response.json()["code"] == "source_rights_not_cleared"


def test_api_lines_and_enrichment_hidden_when_only_export_is_cleared(
    db_url: str, write_engine: Engine
) -> None:
    seed_extended(
        write_engine,
        rights={"gcf_projects": ("permitted", "example evidence: fixture only, not a review")},
    )
    client = make_client(db_url, source_data_access="public")

    detail = client.get("/api/v1/projects/gcf_projects:FP901").json()

    assert detail["enrichments"] == [] and detail["documents"] == []
    assert {o["observation_key"] for o in detail["financial_observations"]} == {
        "FP901:fa_financing"
    }
    assert client.get("/api/v1/analytics/gcf-timeline").status_code == 403
    assert client.get("/api/v1/documents").status_code == 403
