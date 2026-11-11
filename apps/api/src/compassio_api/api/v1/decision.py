"""Task 008 decision-engine routes: methodology, evidence, comparison, prioritization, scenarios.

Everything except ``/decision/methodology`` is source-derived and goes through ``DataPolicyDep``
(local development only until a source's rights are cleared).
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from compassio_api.api.deps import DataPolicyDep, SessionDep
from compassio_api.api.errors import InvalidQueryError, error_responses
from compassio_api.schemas.decision import (
    ApprovedDisbursedResponse,
    ClimateDistributionResponse,
    CompareRequest,
    CompareResponse,
    CountryProfileResponse,
    CoverageResponse,
    EvidenceResponse,
    GroupedFundingResponse,
    InstitutionsResponse,
    MethodologyResponse,
    PrioritizeRequest,
    PrioritizeResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from compassio_api.services.decision import compare as compare_svc
from compassio_api.services.decision import insights
from compassio_api.services.decision.methodology import methodology as methodology_svc
from compassio_api.services.decision.prioritize import prioritize as prioritize_svc
from compassio_api.services.decision.scenario import plan

router = APIRouter()

Iso3 = Annotated[str | None, Query(pattern=r"^[A-Z]{3}$", description="ISO 3166 alpha-3")]
Metric = Annotated[
    str, Query(pattern=r"^[a-z0-9_]{1,80}$", description="See /api/v1/analytics/metrics")
]
Year = Annotated[int | None, Query(ge=1900, le=2100)]
Limit = Annotated[int, Query(ge=1, le=300)]


def _years(year_from: int | None, year_to: int | None) -> None:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise InvalidQueryError("invalid_year_range", "year_from must be <= year_to")


# ------------------------------------------------------------------------------ decision
@router.get(
    "/decision/methodology",
    response_model=MethodologyResponse,
    tags=["decision"],
    summary="Versioned comparison, prioritization and scenario methodologies (no source data)",
)
def methodology() -> MethodologyResponse:
    return methodology_svc()


@router.get(
    "/decision/evidence/{project_id}",
    response_model=EvidenceResponse,
    tags=["decision"],
    summary="Decision evidence for one record: labelled financial facts, provenance, quality",
    responses=error_responses(403, 404, 422, 503),
)
def evidence(
    session: SessionDep,
    policy: DataPolicyDep,
    project_id: Annotated[str, Path(min_length=3, max_length=240)],
) -> EvidenceResponse:
    return compare_svc.evidence(session, policy, project_id)


@router.post(
    "/decision/compare",
    response_model=CompareResponse,
    tags=["decision"],
    summary="Compare 2-10 records side by side (comparable figures grouped; no invented totals)",
    responses=error_responses(403, 404, 422, 503),
)
def compare(body: CompareRequest, session: SessionDep, policy: DataPolicyDep) -> CompareResponse:
    return compare_svc.compare(session, policy, body.project_ids)


@router.post(
    "/decision/prioritize",
    response_model=PrioritizeResponse,
    tags=["decision"],
    summary="Rank records for further due diligence with explainable, user-weighted criteria",
    responses=error_responses(403, 404, 422, 503),
)
def prioritize(
    body: PrioritizeRequest, session: SessionDep, policy: DataPolicyDep
) -> PrioritizeResponse:
    return prioritize_svc(session, policy, body)


@router.post(
    "/decision/scenarios",
    response_model=ScenarioResponse,
    tags=["decision"],
    summary="Hypothetical budget allocation over selected records (planning simulation only)",
    responses=error_responses(403, 404, 422, 503),
)
def scenarios(
    body: ScenarioRequest, session: SessionDep, policy: DataPolicyDep
) -> ScenarioResponse:
    return plan(session, policy, body)


# ----------------------------------------------------------------------------- insights
@router.get(
    "/analytics/funding-by-country",
    response_model=GroupedFundingResponse,
    tags=["analytics"],
    summary="One metric's totals per country (single-country records or source country lines)",
    responses=error_responses(403, 404, 422, 503),
)
def funding_by_country(
    session: SessionDep,
    policy: DataPolicyDep,
    metric: Metric,
    year_from: Year = None,
    year_to: Year = None,
    limit: Limit = 50,
) -> GroupedFundingResponse:
    _years(year_from, year_to)
    return insights.funding_by(session, policy, metric, "country", year_from, year_to, limit)


@router.get(
    "/analytics/funding-by-sector",
    response_model=GroupedFundingResponse,
    tags=["analytics"],
    summary="One metric's totals per source-stated sector",
    responses=error_responses(403, 404, 422, 503),
)
def funding_by_sector(
    session: SessionDep,
    policy: DataPolicyDep,
    metric: Metric,
    year_from: Year = None,
    year_to: Year = None,
    limit: Limit = 50,
) -> GroupedFundingResponse:
    _years(year_from, year_to)
    return insights.funding_by(session, policy, metric, "sector", year_from, year_to, limit)


@router.get(
    "/analytics/institutions",
    response_model=InstitutionsResponse,
    tags=["analytics"],
    summary="Record counts per institution and role (funder, fund, implementer; no money)",
    responses=error_responses(403, 422, 503),
)
def institutions(
    session: SessionDep, policy: DataPolicyDep, country: Iso3 = None, limit: Limit = 20
) -> InstitutionsResponse:
    return insights.institutions(session, policy, country, limit)


@router.get(
    "/analytics/approved-vs-disbursed",
    response_model=ApprovedDisbursedResponse,
    tags=["analytics"],
    summary="Approved (or committed) vs disbursed USD over records reporting both",
    responses=error_responses(403, 422, 503),
)
def approved_vs_disbursed(
    session: SessionDep, policy: DataPolicyDep, country: Iso3 = None
) -> ApprovedDisbursedResponse:
    return insights.approved_vs_disbursed(session, policy, country)


@router.get(
    "/analytics/climate-distribution",
    response_model=ClimateDistributionResponse,
    tags=["analytics"],
    summary="Record counts by climate label or classification (not measured impact)",
    responses=error_responses(403, 422, 503),
)
def climate_distribution(
    session: SessionDep, policy: DataPolicyDep, country: Iso3 = None
) -> ClimateDistributionResponse:
    return insights.climate_distribution(session, policy, country)


@router.get(
    "/analytics/coverage",
    response_model=CoverageResponse,
    tags=["analytics"],
    summary="Per-source coverage, years, rights status and data freshness",
    responses=error_responses(403, 503),
)
def coverage(session: SessionDep, policy: DataPolicyDep) -> CoverageResponse:
    return insights.coverage(session, policy)


@router.get(
    "/analytics/country-profile/{iso3}",
    response_model=CountryProfileResponse,
    tags=["analytics"],
    summary="Country funding profile (e.g. PAK): counts, every metric, sectors, climate labels",
    responses=error_responses(403, 422, 503),
)
def country_profile(
    session: SessionDep,
    policy: DataPolicyDep,
    iso3: Annotated[str, Path(pattern=r"^[A-Z]{3}$")],
) -> CountryProfileResponse:
    return insights.country_profile(session, policy, iso3)
