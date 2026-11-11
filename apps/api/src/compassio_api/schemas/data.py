"""Response schemas for source-derived data routes (projects, sources, filters, analytics).

Money is ``Decimal`` and serialises as a JSON **string** (exact; never a binary float).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class ErrorResponse(_Out):
    code: str
    message: str


class AccessNotice(_Out):
    mode: Literal["local_development", "hackathon_event", "public"]
    notice: str


class PageMeta(_Out):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class CountryOut(_Out):
    country_name: str
    iso3: str | None
    mapping_method: str


class AnnotationOut(_Out):
    scheme: str
    kind: Literal["research_annotation", "source_classification"]
    annotation_source_id: str
    is_model_prediction: Literal[False]
    overall: int | None
    mitigation: int | None
    adaptation: int | None
    is_climate_related: bool | None
    label: str | None
    raw_value: str | None
    provenance: str


class ProjectSummary(_Out):
    id: str
    source_id: str
    source_project_id: str
    record_level: str
    title: str
    description_excerpt: str | None
    countries: list[CountryOut]
    multi_country: bool
    region: str | None
    sector_name: str | None
    year: int | None
    year_type: str | None
    status: str | None
    climate_annotations: list[AnnotationOut]


class ProjectPage(_Out):
    items: list[ProjectSummary]
    pagination: PageMeta
    applied_filters: dict[str, Any]
    sort: str
    access: AccessNotice
    empty_result_message: str | None = None


class SourceRef(_Out):
    source_id: str
    name: str
    publisher: str
    rights_status: str
    reference_url: str | None


class ObservationOut(_Out):
    observation_key: str
    flow_kind: str
    metric_label: str
    level: str
    financing_type: str | None
    is_component: bool
    amount: Decimal | None = Field(description="Exact decimal as a string; null = not reported")
    raw_value: str | None
    value_status: Literal["reported", "not_reported", "unparseable", "invalid"]
    unit: str | None
    currency: str | None
    unit_status: str
    price_basis: str
    effective_date: date | None
    effective_year: int | None
    date_meaning: str
    multi_country: bool
    estimated: bool | None
    recommended_for_aggregates: bool | None
    source_reference: str


class WarningOut(_Out):
    code: str
    field: str | None
    message: str


class RelationshipOut(_Out):
    direction: Literal["outgoing", "incoming"]
    other_project_id: str
    other_source_id: str
    other_title: str
    relation_type: str
    status: str
    method: str
    evidence: str
    human_reviewed: bool


class GroupOut(_Out):
    group_key: str
    meaning: str | None
    member_count: int
    member_ids: list[str] = Field(description="Up to 50 members, ordered by id")


class EnrichmentOut(_Out):
    source_id: str
    snapshot_id: str
    relation_type: str
    match_method: str
    match_evidence: str
    verification_state: str
    review_status: str
    last_verified_on: date
    official_url: str | None
    approval_date: date | None
    approval_date_type: str | None
    approval_status: str | None
    project_status: str | None
    status_as_of: datetime | None
    status_as_of_meaning: str | None
    values: dict[str, Any]
    conflicts: list[dict[str, Any]]
    precedence: str


class DocumentOut(_Out):
    id: str
    source_id: str
    title: str
    family_name: str | None
    document_type: str | None
    publisher_fund: str | None
    document_date: date | None
    document_date_type: str | None
    geographies: list[str]
    languages: str | None
    catalogue_url: str | None
    content_url: str | None
    linked_project_ids: list[str]
    rights_notice: str


class DocumentLinkOut(_Out):
    document: DocumentOut
    relation_type: str
    match_method: str
    match_evidence: str
    verification_state: str
    review_status: str
    last_verified_on: date


class ProjectDetail(_Out):
    id: str
    source: SourceRef
    source_project_id: str
    record_level: str
    title: str
    description: str | None
    recipient_label: str | None
    countries: list[CountryOut]
    multi_country: bool
    region: str | None
    sector_name: str | None
    sector_code: str | None
    sector_vocabulary: str | None
    year: int | None
    year_type: str | None
    date_value: date | None
    date_precision: str | None
    date_estimated: bool | None
    status: str | None
    source_reference: str
    attributes: dict[str, Any]
    climate_annotations: list[AnnotationOut]
    financial_observations: list[ObservationOut]
    data_quality_warnings: list[WarningOut]
    group: GroupOut | None
    relationships: list[RelationshipOut]
    disclaimers: list[str]
    access: AccessNotice
    enrichments: list[EnrichmentOut] = Field(default_factory=list)
    documents: list[DocumentLinkOut] = Field(default_factory=list)


class SourceOut(_Out):
    source_id: str
    name: str
    publisher: str
    version_info: str | None
    file_sha256: str
    reference_url: str | None
    rights_status: str
    rights_evidence: str | None
    license_notes: str | None
    observation_type: str
    audited_record_count: int | None
    imported_project_rows: int
    served_in_current_mode: bool
    public_display_permitted: bool


class SourcesResponse(_Out):
    sources: list[SourceOut]
    access: AccessNotice


class FilterCountry(_Out):
    iso3: str
    name: str
    project_rows: int


class FilterSector(_Out):
    source_id: str
    sector_vocabulary: str | None
    sector_name: str
    project_rows: int


class FilterYearRange(_Out):
    source_id: str
    year_type: str | None
    min_year: int | None
    max_year: int | None
    rows_with_year: int
    rows_without_year: int


class FiltersResponse(_Out):
    sources: list[str]
    countries: list[FilterCountry]
    sectors: list[FilterSector]
    year_ranges: list[FilterYearRange]
    climate_annotation_filter: str
    sort_options: list[str]
    access: AccessNotice


class SourceOverview(_Out):
    source_id: str
    record_level: str
    project_rows: int
    distinct_groups: int
    rows_with_description: int
    rows_with_year: int
    min_year: int | None
    max_year: int | None
    multi_country_rows: int
    pakistan_rows: int
    observations_by_flow: dict[str, dict[str, int]]
    climate_annotations: dict[str, int]
    top_warnings: dict[str, int]


class OverviewResponse(_Out):
    sources: list[SourceOverview]
    cross_source_links: dict[str, int]
    counting_rules: list[str]
    disclaimers: list[str]
    access: AccessNotice


class MetricOut(_Out):
    metric_id: str
    label: str
    source_id: str
    flow_kind: str
    level: str
    currency: str | None
    price_basis: str
    year_basis: str
    is_funding: bool
    description: str
    limitations: list[str]
    deduplication_policy: str
    row_selection: str = Field(
        description="exclude = stated totals only; instrument_lines / country_breakdown = the "
        "source's own component lines"
    )


class MetricsResponse(_Out):
    metrics: list[MetricOut]
    access: AccessNotice


class TrendPoint(_Out):
    year: int
    status: Literal["available", "unavailable"]
    total: Decimal | None
    unit: str | None
    summed_records: int
    missing_value_records: int
    estimated_records: int
    excluded_records: dict[str, int]
    unavailable_reason: str | None


class TrendsResponse(_Out):
    metric: MetricOut
    status: Literal["available", "unavailable"]
    unavailable_reason: str | None
    country: str | None
    year_from: int | None
    year_to: int | None
    points: list[TrendPoint]
    undated_records: int
    excluded_outside_rules: dict[str, int]
    aggregation_limitations: list[str]
    disclaimers: list[str]
    access: AccessNotice
