"""Task 008 decision-engine contracts: comparison, evidence, insights, prioritization, scenarios.

Money is always an exact ``Decimal`` (serialised as a JSON string) together with its flow kind,
level, currency, unit and price basis. ``null`` means "not reported / not determinable", never 0.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from compassio_api.schemas.data import AccessNotice, AnnotationOut, PageMeta, WarningOut


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


FinancialMeaning = Literal[
    "historical_commitment",
    "pledge_not_commitment",
    "approval",
    "disbursement",
    "repayment_not_funding",
    "co_financing",
    "total_project_cost",
    "readiness_grant",
    "deposit_into_fund",
]
FactType = Literal["source_reported", "derived_sum_of_source_transactions"]
CountryAttribution = Literal[
    "single_country_project",
    "whole_project_value_not_attributable_to_one_country",
    "source_published_country_line",
    "no_mapped_country",
]
ProjectIdList = list[str]


# ------------------------------------------------------------------------------- facts
class FinancialFact(_Out):
    fact_id: str = Field(description="observation_key, or derived:<source>:<flow>:<project>")
    fact_type: FactType
    source_id: str
    flow_kind: str
    financial_meaning: FinancialMeaning
    is_funding_flow: bool = Field(
        description="False for repayments, pledges and total project cost (not funding provided)"
    )
    meaning_label: str
    level: str
    financing_type: str | None
    is_component: bool
    amount: Decimal | None = Field(description="Exact source value in `unit`; null = not reported")
    amount_in_units: Decimal | None = Field(description="amount x unit scale; null if unknown")
    unit: str | None
    currency: str | None = Field(description="ISO 4217; null = not stated by the source")
    price_basis: str
    value_status: str
    date: date | None
    year: int | None
    date_meaning: str
    multi_country: bool
    country_iso3: str | None
    country_attribution: CountryAttribution
    estimated: bool | None
    recommended_for_aggregates: bool | None
    transactions_summed: int | None = Field(
        default=None, description="Derived sums only: number of source transactions"
    )
    first_year: int | None = None
    last_year: int | None = None
    comparability_key: str = Field(
        description="Facts are comparable (and summable across projects) only with equal keys"
    )
    source_reference: str


class SourceInfo(_Out):
    source_id: str
    name: str
    publisher: str
    rights_status: str
    access_tier: str
    reference_url: str | None


class CountryRef(_Out):
    country_name: str
    iso3: str | None
    mapping_method: str


class SectorRef(_Out):
    name: str
    code: str | None
    vocabulary: str | None


class InstitutionRef(_Out):
    role: str = Field(description="What this institution is in the source (funder, fund, ...)")
    name: str


class VerifiedApproval(_Out):
    approval_status: str | None
    approval_date: date | None
    approval_date_type: str | None
    project_status: str | None
    status_as_of: datetime | None
    verified_by_source_id: str
    verification_state: str
    official_url: str | None


class ClimateRelevance(_Out):
    status: Literal[
        "research_annotation_climate_related",
        "research_annotation_not_climate_related",
        "listed_by_climate_fund",
        "no_climate_annotation",
    ]
    basis: str
    is_model_prediction: Literal[False] = False
    statement: str = Field(
        default="A climate-relevance label or classification, not measured environmental impact."
    )
    annotations: list[AnnotationOut]
    model_screening: str = Field(
        default="Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
    )


class LinkedRecord(_Out):
    project_id: str
    source_id: str
    title: str
    relation_type: str
    status: str
    verification_state: str
    human_reviewed: bool
    double_counting_rule: str


class DocumentRef(_Out):
    document_id: str
    title: str
    document_type: str | None
    verification_state: str
    catalogue_url: str | None


class Completeness(_Out):
    has_description: bool
    has_sector: bool
    has_year: bool
    has_mapped_country: bool
    has_source_status: bool
    has_institution: bool
    has_reported_amount: bool
    has_amount_with_currency: bool
    has_dated_amount: bool
    has_documents: bool
    has_verified_approval: bool
    missing: list[str] = Field(description="Names of the indicators above that are false")


class ProjectEvidence(_Out):
    project_id: str
    title: str
    source: SourceInfo
    source_project_id: str
    record_level: str
    description: str | None
    countries: list[CountryRef]
    multi_country: bool
    country_note: str
    sector: SectorRef | None
    institutions: list[InstitutionRef]
    year: int | None
    year_type: str | None
    source_status: str | None = Field(description="Lifecycle status as the source states it")
    verified_approval: VerifiedApproval | None = Field(
        description="Only when an approval is published by an official source (GCF API)"
    )
    climate_relevance: ClimateRelevance
    headline_facts: list[FinancialFact] = Field(
        description="Stated project totals and derived per-flow transaction sums"
    )
    breakdown_facts: list[FinancialFact] = Field(
        description="Instrument components and source-published country lines (never added "
        "to the headline totals)"
    )
    linked_records: list[LinkedRecord]
    documents: list[DocumentRef]
    data_quality_warnings: list[WarningOut]
    completeness: Completeness
    source_reference: str
    group_key: str | None = Field(
        description="Source-published record group (e.g. AidData parent package)"
    )
    group_meaning: str | None
    current_funding_opportunity: Literal["not_determinable"] = Field(
        default="not_determinable",
        description="Compassio holds no data on open calls; historical records are not offers",
    )
    limitations: list[str]


class EvidenceResponse(_Out):
    project: ProjectEvidence
    methodology_version: str
    disclaimers: list[str]
    access: AccessNotice


# --------------------------------------------------------------------------- comparison
class CompareRequest(_In):
    project_ids: ProjectIdList = Field(min_length=2, max_length=10)

    @field_validator("project_ids")
    @classmethod
    def _ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("project_ids must be unique")
        for pid in value:
            if not 3 <= len(pid) <= 240:
                raise ValueError("each project id must be 3-240 characters")
        return value


class ComparisonCell(_Out):
    project_id: str
    facts: list[FinancialFact] = Field(description="Empty = not reported for this project")


class ComparisonGroup(_Out):
    comparability_key: str
    source_id: str
    flow_kind: str
    financial_meaning: FinancialMeaning
    meaning_label: str
    level: str
    currency: str | None
    price_basis: str
    cells: list[ComparisonCell]
    selection_total: Decimal | None = Field(
        description="Sum across the selected projects, in units of `currency`; null if unsafe"
    )
    selection_total_status: Literal["available", "unavailable"]
    selection_summed_records: int
    selection_missing_records: int = Field(
        description="Selected records whose figure is not reported (excluded, never zero)"
    )
    selection_total_reason: str | None
    selection_total_meaning: str


class DuplicateWarning(_Out):
    project_ids: list[str]
    relation_type: str
    verification_state: str
    message: str


class CompareResponse(_Out):
    projects: list[ProjectEvidence]
    comparable_groups: list[ComparisonGroup]
    duplicate_warnings: list[DuplicateWarning]
    field_matrix: dict[str, dict[str, bool]] = Field(
        description="indicator -> project_id -> present (explicit missing-information view)"
    )
    methodology_version: str
    disclaimers: list[str]
    access: AccessNotice


# ----------------------------------------------------------------------------- insights
class MetricDeclaration(_Out):
    metric_id: str
    label: str
    universe: str
    financial_meaning: str
    source_id: str
    flow_kind: str
    level: str
    currency: str | None
    price_basis: str
    unit: str | None
    year_basis: str
    is_funding: bool
    known_exclusions: list[str]
    excluded_records: dict[str, int] = Field(description="Records left out, by reason (counted)")


class GroupedTotal(_Out):
    key: str
    label: str
    status: Literal["available", "unavailable"]
    total: Decimal | None
    summed_records: int
    missing_value_records: int
    estimated_records: int
    unavailable_reason: str | None


class GroupedFundingResponse(_Out):
    dimension: Literal["country", "sector"]
    status: Literal["available", "unavailable"]
    unavailable_reason: str | None
    declaration: MetricDeclaration
    year_from: int | None
    year_to: int | None
    groups: list[GroupedTotal]
    groups_total: int
    groups_shown: int
    disclaimers: list[str]
    access: AccessNotice


class InstitutionCount(_Out):
    institution: str
    projects: int


class InstitutionGroup(_Out):
    source_id: str
    role: str
    field: str
    institutions: list[InstitutionCount]
    distinct_institutions: int
    projects_without_institution: int
    projects: int


class InstitutionsResponse(_Out):
    universe: str
    country: str | None
    measure: Literal["project_record_count"]
    groups: list[InstitutionGroup]
    note: str
    access: AccessNotice


class ApprovedDisbursedSource(_Out):
    source_id: str
    approval_meaning: str
    disbursement_meaning: str
    currency: str
    universe: str
    projects_with_approval: int
    projects_with_disbursement: int
    paired_projects: int
    approved_total_paired: Decimal | None
    disbursed_total_paired: Decimal | None
    disbursed_to_approved_ratio: Decimal | None = Field(
        description="Within paired projects only; disbursement recording differs by source"
    )
    excluded_projects: dict[str, int]
    limitations: list[str]


class ApprovedDisbursedResponse(_Out):
    country: str | None
    sources: list[ApprovedDisbursedSource]
    disclaimers: list[str]
    access: AccessNotice


class DistributionBucket(_Out):
    label: str
    projects: int


class ClimateDistribution(_Out):
    scheme: str
    annotation_source_id: str
    kind: Literal["research_annotation", "source_classification"]
    meaning: str
    buckets: list[DistributionBucket]
    projects_annotated: int


class ClimateDistributionResponse(_Out):
    country: str | None
    measure: Literal["project_record_count"]
    distributions: list[ClimateDistribution]
    statement: str
    access: AccessNotice


class SourceCoverage(_Out):
    source_id: str
    name: str
    publisher: str
    rights_status: str
    access_tier: str
    served_in_current_mode: bool
    version_info: str | None
    project_rows: int
    financial_observation_rows: int
    reported_amount_rows: int
    min_year: int | None
    max_year: int | None
    last_completed_import: datetime | None
    snapshot_ids: list[str]


class CoverageResponse(_Out):
    data_version: list[int] = Field(description="[latest completed import id, completed runs]")
    sources: list[SourceCoverage]
    access: AccessNotice


class CountryMetricSummary(_Out):
    declaration: MetricDeclaration
    status: Literal["available", "unavailable"]
    all_years_total: Decimal | None
    summed_records: int
    first_year: int | None
    last_year: int | None
    unavailable_reason: str | None


class SourceCount(_Out):
    source_id: str
    single_country_projects: int
    multi_country_projects_including_country: int


class CountryProfileResponse(_Out):
    country: str
    project_counts: list[SourceCount]
    metrics: list[CountryMetricSummary]
    top_sectors: list[DistributionBucket]
    climate: ClimateDistributionResponse
    country_aggregates_endpoint: str
    disclaimers: list[str]
    access: AccessNotice


# ------------------------------------------------------------------------ prioritization
class PriorityWeights(_In):
    climate_relevance: Decimal = Field(default=Decimal(3), ge=0, le=10)
    evidence_completeness: Decimal = Field(default=Decimal(2), ge=0, le=10)
    funding_completeness: Decimal = Field(default=Decimal(2), ge=0, le=10)
    sector_match: Decimal = Field(default=Decimal(1), ge=0, le=10)
    country_match: Decimal = Field(default=Decimal(1), ge=0, le=10)
    documentation: Decimal = Field(default=Decimal(1), ge=0, le=10)
    review_uncertainty: Decimal = Field(default=Decimal(0), ge=0, le=10)


class CandidateFilters(_In):
    q: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    source: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,80}$")
    sector: str | None = Field(default=None, min_length=1, max_length=200)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)
    project_ids: list[str] | None = Field(default=None, min_length=1, max_length=500)


class PrioritizeRequest(_In):
    filters: CandidateFilters = Field(default_factory=CandidateFilters)
    weights: PriorityWeights = Field(default_factory=PriorityWeights)
    sectors_of_interest: list[str] = Field(default_factory=list, max_length=20)
    countries_of_interest: list[str] = Field(default_factory=list, max_length=20)
    missing_component_policy: Literal["score_zero", "exclude_from_denominator"] = "score_zero"
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=25, ge=1, le=100)

    @field_validator("countries_of_interest")
    @classmethod
    def _iso(cls, value: list[str]) -> list[str]:
        for v in value:
            if len(v) != 3 or not v.isupper() or not v.isalpha():
                raise ValueError("countries_of_interest must be ISO 3166 alpha-3 codes")
        return value


class ScoreComponent(_Out):
    criterion: str
    weight: Decimal
    value: Decimal | None = Field(description="0-1; null = not applicable / not available")
    status: Literal["applied", "not_available", "not_requested"]
    contribution: Decimal = Field(description="weight x value (0 when not applied)")
    evidence: str


class RelevanceDistinction(_Out):
    matches_search: bool = True
    matched_filters: dict[str, str | int | list[str]]
    has_documented_historical_funding: bool
    documented_funding_basis: str
    current_funding_opportunity: Literal["not_determinable"] = "not_determinable"


class PriorityItem(_Out):
    rank: int
    project_id: str
    title: str
    source_id: str
    score: Decimal = Field(description="Σ contributions / Σ applied weights, 0-1, 4 dp")
    components: list[ScoreComponent]
    applied_weight_total: Decimal
    distinctions: RelevanceDistinction
    interpretation: str


class PrioritizeResponse(_Out):
    items: list[PriorityItem]
    pagination: PageMeta
    candidates: int
    methodology_version: str
    ranking_fingerprint: str = Field(
        description="sha256 of methodology, canonical request (without page) and data version"
    )
    data_version: list[int]
    disclaimers: list[str]
    access: AccessNotice


# ------------------------------------------------------------------------------ scenarios
SUPPORTED_OBJECTIVES = ("allocate_by_weights",)
UNSUPPORTED_OBJECTIVES = {
    "maximize_return": "Compassio holds no return or profit data.",
    "maximize_emission_reductions": "No measured emission reductions are stored.",
    "minimize_cost_per_tonne": "No verified project cost or emissions data are stored.",
    "maximize_climate_impact": "Climate labels are classifications, not measured impact.",
    "maximize_risk_reduction": "No climate-risk reduction measurements are stored.",
    "fund_full_project_cost": "No verified remaining-cost or funding-gap data are stored.",
}


class Budget(_In):
    amount: Decimal = Field(gt=0, le=Decimal("1e15"), max_digits=30, decimal_places=6)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    unit: Literal["units", "thousands", "millions"] = "units"


class ScenarioConstraints(_In):
    min_per_project: Decimal | None = Field(default=None, ge=0, max_digits=30, decimal_places=6)
    max_per_project: Decimal | None = Field(default=None, gt=0, max_digits=30, decimal_places=6)
    max_share_per_sector: Decimal | None = Field(default=None, gt=0, le=1)
    max_share_per_country: Decimal | None = Field(default=None, gt=0, le=1)


class ScenarioRequest(_In):
    budget: Budget
    project_ids: ProjectIdList = Field(min_length=1, max_length=50)
    method: Literal["equal", "sector_priority", "priority_score"] = "equal"
    objective: str = Field(default="allocate_by_weights", max_length=60)
    sector_priorities: dict[str, Decimal] = Field(default_factory=dict, max_length=50)
    unlisted_sector_weight: Decimal = Field(default=Decimal(0), ge=0, le=100)
    priority_weights: PriorityWeights = Field(default_factory=PriorityWeights)
    constraints: ScenarioConstraints = Field(default_factory=ScenarioConstraints)
    scenario_label: str | None = Field(default=None, max_length=120)

    @field_validator("project_ids")
    @classmethod
    def _ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("project_ids must be unique")
        return value

    @field_validator("sector_priorities")
    @classmethod
    def _weights(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        for k, v in value.items():
            if not 1 <= len(k) <= 200 or v < 0 or v > 100:
                raise ValueError("sector weights must be 0-100 with 1-200 character names")
        return value


class Allocation(_Out):
    project_id: str
    title: str
    source_id: str
    sector: str | None
    country_group: str
    weight: Decimal
    weight_basis: str
    allocation: Decimal = Field(description="In the budget currency and unit")
    share_of_budget: Decimal
    binding_constraints: list[str]
    reference_facts: list[FinancialFact] = Field(
        description="Historical recorded figures for context; NOT costs or funding needs"
    )
    warnings: list[str]


class ScenarioResponse(_Out):
    scenario_label: str | None
    status: Literal["allocated", "partially_allocated", "infeasible"]
    budget: Budget
    allocated_total: Decimal
    unallocated: Decimal
    conservation_check: str
    allocations: list[Allocation]
    arithmetic: list[str]
    feasibility_warnings: list[str]
    assumptions: list[str]
    disclosures: list[str]
    methodology_version: str
    request_sha256: str
    result_sha256: str
    data_version: list[int]
    access: AccessNotice


# ---------------------------------------------------------------------------- methodology
class MethodologyResponse(_Out):
    comparison_version: str
    priority_version: str
    scenario_version: str
    priority_criteria: dict[str, str]
    scenario_methods: dict[str, str]
    supported_objectives: list[str]
    unsupported_objectives: dict[str, str]
    financial_meanings: dict[str, str]
    rules: list[str]
    public_display: dict[str, str]
