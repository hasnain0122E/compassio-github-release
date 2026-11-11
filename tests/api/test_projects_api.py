"""Project search, filters, pagination, detail and error contracts (artificial database)."""

import pytest
from fastapi.testclient import TestClient

from .conftest import make_client

URL = "/api/v1/projects"


@pytest.fixture
def client(data_client: TestClient) -> TestClient:
    """Module-local: the seeded ARTIFICIAL database client (shadows the root fixture)."""
    return data_client


def _ids(client: TestClient, query: str) -> list[str]:
    response = client.get(f"{URL}?page_size=100&{query}")
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_list_envelope_and_local_access_notice(client: TestClient) -> None:
    response = client.get(URL)
    body = response.json()

    assert response.status_code == 200
    assert response.headers["X-Compassio-Data-Access"] == "local_development"
    assert set(body) == {
        "items",
        "pagination",
        "applied_filters",
        "sort",
        "access",
        "empty_result_message",
    }
    assert body["pagination"] == {"page": 1, "page_size": 25, "total_items": 12, "total_pages": 1}
    assert body["access"]["mode"] == "local_development"
    assert "LOCAL DEVELOPMENT ONLY" in body["access"]["notice"]


@pytest.mark.parametrize("query", ["page=0", "page_size=0", "page_size=101", "page=100001"])
def test_pagination_bounds_are_validated(client: TestClient, query: str) -> None:
    assert client.get(f"{URL}?{query}").status_code == 422


def test_pages_partition_results_deterministically(client: TestClient) -> None:
    pages = [
        [i["id"] for i in client.get(f"{URL}?page_size=5&page={n}&sort=-year").json()["items"]]
        for n in (1, 2, 3)
    ]
    flat = [i for page in pages for i in page]

    assert len(flat) == 12 and len(set(flat)) == 12
    assert pages == [
        [i["id"] for i in client.get(f"{URL}?page_size=5&page={n}&sort=-year").json()["items"]]
        for n in (1, 2, 3)
    ]
    beyond = client.get(f"{URL}?page_size=5&page=4").json()
    assert beyond["items"] == [] and "beyond the last page" in beyond["empty_result_message"]


def test_sort_by_year_puts_undated_records_last(client: TestClient) -> None:
    years = [i["year"] for i in client.get(f"{URL}?page_size=100&sort=-year").json()["items"]]
    dated = [y for y in years if y is not None]

    assert dated == sorted(dated, reverse=True)
    assert years[len(dated) :] == [None] * (len(years) - len(dated))


def test_filters_country_source_year_sector_climate(client: TestClient) -> None:
    assert _ids(client, "source=gcf_projects") == ["gcf_projects:FP901", "gcf_projects:FP902"]
    assert "aiddata:4" not in _ids(client, "country=ZZA")  # regional record has no ISO3
    assert set(_ids(client, "country=ZZB")) == {
        "aiddata:5",
        "climate_funds_update:projects-r4",
        "gcf_projects:FP902",
    }
    assert _ids(client, "source=aiddata&year_from=2011&year_to=2014") == ["aiddata:2", "aiddata:3"]
    assert _ids(client, "sector=EXAMPLE%20ENERGY") == ["aiddata:1"]
    assert _ids(client, "climate_related=true") == ["aiddata:1"]
    assert "gcf_projects:FP901" not in _ids(client, "climate_related=false")  # no rio annotation


def test_text_search_is_literal_and_case_insensitive(client: TestClient) -> None:
    assert _ids(client, "q=EXAMPLE_SOLAR") == ["aiddata:1"]
    assert _ids(client, "q=0%25") == ["aiddata:1"]  # literal "0%" (title contains "100%")
    assert _ids(client, "q=done_ok") == ["aiddata:1"]
    assert _ids(client, "q=done%25ok") == []  # % is not a wildcard
    assert _ids(client, "q=d_ne") == []  # _ is not a wildcard (would match "done")


@pytest.mark.parametrize(
    "q", ["' OR 1=1 --", "'; DROP TABLE projects; --", '" OR ""="', "\\", "%' OR '%'='"]
)
def test_search_injection_attempts_are_inert(client: TestClient, q: str) -> None:
    response = client.get(URL, params={"q": q})

    assert response.status_code == 200
    assert response.json()["pagination"]["total_items"] == 0
    assert client.get(URL).json()["pagination"]["total_items"] == 12  # table intact


def test_empty_result_is_explicit(client: TestClient) -> None:
    body = client.get(f"{URL}?q=example_nothing_matches").json()

    assert body["items"] == []
    assert body["pagination"]["total_items"] == 0 and body["pagination"]["total_pages"] == 0
    assert body["empty_result_message"] == "No project records match these filters."


@pytest.mark.parametrize(
    "query",
    [
        "year_from=2015&year_to=2010",
        "year_from=1800",
        "year_to=2200",
        "country=zza",
        "country=ZZAA",
        "source=Bad-Source",
        "sort=amount",
        "climate_related=maybe",
        "q=" + "x" * 201,
    ],
)
def test_invalid_query_parameters_return_422(client: TestClient, query: str) -> None:
    response = client.get(f"{URL}?{query}")

    assert response.status_code == 422


def test_invalid_year_range_has_explicit_code(client: TestClient) -> None:
    body = client.get(f"{URL}?year_from=2015&year_to=2010").json()

    assert body == {"code": "invalid_year_range", "message": "year_from must be <= year_to"}


def test_detail_contains_provenance_finance_warnings_group_and_links(client: TestClient) -> None:
    detail = client.get(f"{URL}/aiddata:3").json()

    assert detail["source"]["source_id"] == "aiddata"
    assert detail["source"]["rights_status"] == "not_reviewed"
    assert detail["group"]["group_key"] == "aiddata_parent:77"
    assert detail["group"]["member_ids"] == ["aiddata:2", "aiddata:3"]
    amounts = {o["observation_key"]: o for o in detail["financial_observations"]}
    missing = amounts["3:amount_original_currency"]
    assert missing["amount"] is None and missing["value_status"] == "not_reported"
    assert "amount_not_reported" in {w["code"] for w in detail["data_quality_warnings"]}
    assert len(detail["disclaimers"]) == 5

    gcf = client.get(f"{URL}/gcf_projects:FP901").json()
    assert gcf["relationships"][0]["other_project_id"] == "climate_funds_update:projects-r2"
    assert gcf["relationships"][0]["direction"] == "incoming"
    assert gcf["relationships"][0]["status"] == "probable_match_reference_code"
    assert gcf["climate_annotations"][0]["is_model_prediction"] is False


def test_money_is_serialised_as_exact_decimal_strings(client: TestClient) -> None:
    detail = client.get(f"{URL}/aiddata:1").json()
    amounts = {o["observation_key"]: o["amount"] for o in detail["financial_observations"]}

    assert amounts["1:amount_original_currency"] == "100.10"
    assert amounts["1:amount_constant_usd_2021"] == "200.25"


def test_missing_project_is_404_with_code(client: TestClient) -> None:
    response = client.get(f"{URL}/aiddata:does_not_exist")

    assert response.status_code == 404
    assert response.json()["code"] == "project_not_found"


def test_missing_database_returns_503_but_health_still_works(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    client = make_client(f"sqlite:///{(tmp_path / 'absent.sqlite').as_posix()}")

    assert client.get("/health").status_code == 200
    response = client.get(URL)
    assert response.status_code == 503
    assert response.json()["code"] == "database_not_ready"


def test_existing_system_endpoints_are_unchanged(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/meta").json()["tagline"] == "Give Funding a Better Direction."
