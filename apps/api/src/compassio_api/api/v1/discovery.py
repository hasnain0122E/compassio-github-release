"""Task 006-DB discovery routes (source-derived: local development only until rights clear)."""

from typing import Annotated

from fastapi import APIRouter, Query

from compassio_api.api.deps import DataPolicyDep, SessionDep
from compassio_api.api.errors import error_responses
from compassio_api.schemas.discovery import (
    CountryAggregatesResponse,
    DataQualityResponse,
    DocumentPage,
    FinancingCompletenessResponse,
    GcfTimelineResponse,
    RelationshipSummaryResponse,
)
from compassio_api.services import discovery

router = APIRouter()

Iso3 = Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")]


@router.get(
    "/documents",
    response_model=DocumentPage,
    tags=["documents"],
    summary="Catalogue documents (metadata only), optionally for one project",
    responses=error_responses(403, 422, 503),
)
def documents(
    session: SessionDep,
    policy: DataPolicyDep,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    project_id: Annotated[str | None, Query(min_length=3, max_length=240)] = None,
    fund: Annotated[str | None, Query(pattern=r"^[A-Z]{2,6}$")] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    linked_only: bool = False,
) -> DocumentPage:
    return discovery.list_documents(
        session,
        policy,
        page=page,
        page_size=page_size,
        project_id=project_id,
        fund=fund,
        q=q,
        linked_only=linked_only,
    )


@router.get(
    "/analytics/data-quality",
    response_model=DataQualityResponse,
    tags=["analytics"],
    summary="Per-source field coverage and data-quality warning counts",
    responses=error_responses(403, 503),
)
def data_quality(session: SessionDep, policy: DataPolicyDep) -> DataQualityResponse:
    return discovery.data_quality(session, policy)


@router.get(
    "/analytics/financing-completeness",
    response_model=FinancingCompletenessResponse,
    tags=["analytics"],
    summary="Financial observations by source, flow and value status (counts, no sums)",
    responses=error_responses(403, 503),
)
def financing_completeness(
    session: SessionDep, policy: DataPolicyDep
) -> FinancingCompletenessResponse:
    return discovery.financing_completeness(session, policy)


@router.get(
    "/analytics/gcf-timeline",
    response_model=GcfTimelineResponse,
    tags=["analytics"],
    summary="GCF projects approved per year (dated by the GCF API) with GCF funding",
    responses=error_responses(403, 422, 503),
)
def gcf_timeline(
    session: SessionDep, policy: DataPolicyDep, country: Iso3 = None
) -> GcfTimelineResponse:
    return discovery.gcf_timeline(session, policy, country)


@router.get(
    "/analytics/country-aggregates",
    response_model=CountryAggregatesResponse,
    tags=["analytics"],
    summary="GCF country summary figures (source-published aggregates; never summed)",
    responses=error_responses(403, 422, 503),
)
def country_aggregates(
    session: SessionDep, policy: DataPolicyDep, iso3: Iso3 = None
) -> CountryAggregatesResponse:
    return discovery.country_aggregates(session, policy, iso3)


@router.get(
    "/analytics/relationships",
    response_model=RelationshipSummaryResponse,
    tags=["analytics"],
    summary="Counts of explicit links by type, verification state and asserting source",
    responses=error_responses(403, 503),
)
def relationships(session: SessionDep, policy: DataPolicyDep) -> RelationshipSummaryResponse:
    return discovery.relationship_summary(session, policy)
