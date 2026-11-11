"""Sources, filters, overview and trends (artificial database; values are test inputs)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(data_client: TestClient) -> TestClient:
    """Module-local: the seeded ARTIFICIAL database client (shadows the root fixture)."""
    return data_client


def test_sources_list_rights_status_and_counts(client: TestClient) -> None:
    body = client.get("/api/v1/sources").json()
    by_id = {s["source_id"]: s for s in body["sources"]}

    assert by_id["aiddata"]["imported_project_rows"] == 5
    assert all(s["rights_status"] == "not_reviewed" for s in body["sources"])
    assert not any(s["public_display_permitted"] for s in body["sources"])


def test_filters_reflect_imported_records(client: TestClient) -> None:
    body = client.get("/api/v1/filters").json()

    assert {c["iso3"] for c in body["countries"]} == {"ZZA", "ZZB", "PAK"}
    ranges = {r["source_id"]: r for r in body["year_ranges"]}
    assert ranges["gcf_projects"]["min_year"] is None
    assert ranges["gcf_projects"]["rows_without_year"] == 2
    assert ranges["aiddata"]["min_year"] == 2010 and ranges["aiddata"]["max_year"] == 2015
    assert "not a Compassio model prediction" in body["climate_annotation_filter"]


def test_overview_counts_rows_groups_and_links(client: TestClient) -> None:
    body = client.get("/api/v1/analytics/overview").json()
    by_id = {s["source_id"]: s for s in body["sources"]}

    assert by_id["aiddata"]["project_rows"] == 5
    assert by_id["aiddata"]["distinct_groups"] == 4  # records 2 and 3 share a parent package
    assert by_id["adb_pakistan"]["distinct_groups"] == 1  # two instruments, one ADB project
    assert by_id["gcf_projects"]["multi_country_rows"] == 1
    assert by_id["aiddata"]["climate_annotations"]["rio_marker_qi_et_al_2026:climate_related"] == 1
    assert body["cross_source_links"] == {"probable_match_reference_code": 1}
    assert len(body["disclaimers"]) == 5


def _trend(client: TestClient, query: str) -> dict[str, object]:
    response = client.get(f"/api/v1/analytics/trends?{query}")
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def _points(body: dict[str, object]) -> dict[int, dict[str, object]]:
    points = body["points"]
    assert isinstance(points, list)
    return {p["year"]: p for p in points}


def test_aiddata_trend_excludes_multi_country_pledges_and_counts_missing(
    client: TestClient,
) -> None:
    points = _points(_trend(client, "metric=aiddata_commitments_constant_2021_usd"))

    assert points[2010]["total"] == "200.25"
    assert points[2010]["excluded_records"] == {"multi_country_whole_project_value": 1}
    assert points[2012]["total"] == "200.25"
    assert points[2012]["summed_records"] == 1 and points[2012]["missing_value_records"] == 1
    assert 2015 not in points  # the only 2015 record is a pledge, not a commitment


def test_country_filter_never_attributes_regional_amounts(client: TestClient) -> None:
    points = _points(_trend(client, "metric=aiddata_commitments_constant_2021_usd&country=ZZA"))

    assert points[2010]["total"] == "200.25" and points[2010]["excluded_records"] == {}


def test_cfu_trend_uses_unit_scale_and_excludes_components_and_multi_country(
    client: TestClient,
) -> None:
    points = _points(_trend(client, "metric=cfu_approvals_usd"))

    assert points[2016]["total"] == "1500000.0"  # 1.5 USD millions; Grant component not added
    assert points[2016]["excluded_records"] == {"multi_country_whole_project_value": 1}
    assert points[2017]["total"] == "250000.00"


def test_adb_flows_are_separate_and_repayments_are_not_funding(client: TestClient) -> None:
    commitments = _points(_trend(client, "metric=adb_commitments_usd"))
    disbursements = _points(_trend(client, "metric=adb_disbursements_usd"))
    repayments = _trend(client, "metric=adb_principal_repayments_usd")

    assert commitments[2019]["total"] == "1000"
    assert commitments[2019]["excluded_records"] == {"amount_invalid": 1}
    assert disbursements[2020]["total"] == "390"  # includes the published -10 reversal
    metric = repayments["metric"]
    assert isinstance(metric, dict) and metric["is_funding"] is False


def test_gcf_trend_is_unavailable_not_zero(client: TestClient) -> None:
    body = _trend(client, "metric=gcf_financing")

    assert body["status"] == "unavailable"
    assert body["points"] == []
    assert "no currency or unit" in str(body["unavailable_reason"])


def test_unknown_metric_and_bad_range(client: TestClient) -> None:
    unknown = client.get("/api/v1/analytics/trends?metric=example_unknown")
    assert unknown.status_code == 404 and unknown.json()["code"] == "unknown_metric"
    assert client.get("/api/v1/analytics/trends").status_code == 422
    bad = client.get(
        "/api/v1/analytics/trends?metric=cfu_approvals_usd&year_from=2020&year_to=2010"
    )
    assert bad.status_code == 422


def test_empty_trend_window_is_unavailable(client: TestClient) -> None:
    body = _trend(client, "metric=adb_commitments_usd&year_from=2030")

    assert body["status"] == "unavailable" and body["points"] == []


def test_metrics_catalogue_lists_single_source_metrics(client: TestClient) -> None:
    metrics = client.get("/api/v1/analytics/metrics").json()["metrics"]

    assert {m["metric_id"] for m in metrics} >= {"cfu_approvals_usd", "gcf_financing"}
    assert all(m["source_id"] for m in metrics)
