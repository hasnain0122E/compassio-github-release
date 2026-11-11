from fastapi.testclient import TestClient

from compassio_api import __version__


def test_health_returns_ok_status(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "compassio-api", "version": __version__}


def test_meta_returns_product_identity(client: TestClient) -> None:
    response = client.get("/api/v1/meta")

    assert response.status_code == 200
    assert response.json() == {
        "product_name": "Compassio",
        "tagline": "Give Funding a Better Direction.",
        "category": "Climate Funding Intelligence",
        "api_version": __version__,
        "environment": "test",
    }


def test_unknown_route_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_openapi_schema_lists_only_implemented_paths(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Compassio API"
    assert set(schema["paths"]) == {
        "/health",
        "/api/v1/meta",
        "/api/v1/sources",
        "/api/v1/filters",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}",
        "/api/v1/analytics/overview",
        "/api/v1/analytics/metrics",
        "/api/v1/analytics/trends",
        "/api/v1/documents",
        "/api/v1/analytics/data-quality",
        "/api/v1/analytics/financing-completeness",
        "/api/v1/analytics/gcf-timeline",
        "/api/v1/analytics/country-aggregates",
        "/api/v1/analytics/relationships",
        "/api/v1/models",
        "/api/v1/models/comparison",
        "/api/v1/screening/text",
        "/api/v1/challenges/c09/screen",
        "/api/v1/screening/projects/{project_id}",
        "/api/v1/reviews",
        "/api/v1/reviews/{screening_id}",
        "/api/v1/decision/methodology",
        "/api/v1/decision/evidence/{project_id}",
        "/api/v1/decision/compare",
        "/api/v1/decision/prioritize",
        "/api/v1/decision/scenarios",
        "/api/v1/analytics/funding-by-country",
        "/api/v1/analytics/funding-by-sector",
        "/api/v1/analytics/institutions",
        "/api/v1/analytics/approved-vs-disbursed",
        "/api/v1/analytics/climate-distribution",
        "/api/v1/analytics/coverage",
        "/api/v1/analytics/country-profile/{iso3}",
    }
    # Task 007: screening endpoints exist but serve only in local development (tested in
    # test_screening.py); there is no public prediction service.
    assert not any("predict" in path for path in schema["paths"])
    assert {"HealthResponse", "MetaResponse"} <= set(schema["components"]["schemas"])


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_does_not_allow_unlisted_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_rejects_unlisted_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/meta",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 400
