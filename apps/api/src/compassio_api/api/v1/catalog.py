"""Sources (metadata, always available), filters and analytics (source-derived data)."""

from typing import Annotated

from fastapi import APIRouter, Query

from compassio_api.api.deps import DataPolicyDep, PolicyDep, SessionDep
from compassio_api.api.errors import InvalidQueryError, error_responses
from compassio_api.schemas.data import (
    FiltersResponse,
    MetricsResponse,
    OverviewResponse,
    SourcesResponse,
    TrendsResponse,
)
from compassio_api.services import catalog
from compassio_api.services.finance import trends as compute_trends

router = APIRouter()


@router.get(
    "/sources",
    response_model=SourcesResponse,
    tags=["sources"],
    summary="Registered sources with checksums and rights-review status",
    responses=error_responses(503),
)
def sources(session: SessionDep, policy: PolicyDep) -> SourcesResponse:
    return catalog.list_sources(session, policy)


@router.get(
    "/filters",
    response_model=FiltersResponse,
    tags=["projects"],
    summary="Countries, sectors and year ranges present in the imported records",
    responses=error_responses(403, 503),
)
def filters(session: SessionDep, policy: DataPolicyDep) -> FiltersResponse:
    return catalog.filters(session, policy)


@router.get(
    "/analytics/overview",
    response_model=OverviewResponse,
    tags=["analytics"],
    summary="Per-source counts, coverage, finance availability and links",
    responses=error_responses(403, 503),
)
def overview(session: SessionDep, policy: DataPolicyDep) -> OverviewResponse:
    return catalog.overview(session, policy)


@router.get(
    "/analytics/metrics",
    response_model=MetricsResponse,
    tags=["analytics"],
    summary="Catalogue of single-source financial metrics usable in /analytics/trends",
    responses=error_responses(403, 503),
)
def metrics(policy: DataPolicyDep) -> MetricsResponse:
    return catalog.metrics(policy)


@router.get(
    "/analytics/trends",
    response_model=TrendsResponse,
    tags=["analytics"],
    summary="Yearly totals for one metric; unsafe years are 'unavailable' with a reason",
    responses=error_responses(403, 404, 422, 503),
)
def trends(
    session: SessionDep,
    policy: DataPolicyDep,
    metric: Annotated[str, Query(pattern=r"^[a-z0-9_]{1,80}$")],
    country: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    year_from: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    year_to: Annotated[int | None, Query(ge=1900, le=2100)] = None,
) -> TrendsResponse:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise InvalidQueryError("invalid_year_range", "year_from must be <= year_to")
    return compute_trends(session, policy, metric, country, year_from, year_to)
