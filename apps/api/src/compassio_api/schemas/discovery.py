"""Schemas for Task 006-DB discovery routes. Every numeric aggregate carries ``MeasureMeta``."""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from compassio_api.schemas.data import (
    AccessNotice,
    DocumentOut,
    PageMeta,
    TrendPoint,
)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class MeasureMeta(_Out):
    dataset: str
    source_id: str
    unit_of_observation: str
    measure: str
    currency: str | None
    unit: str | None
    date_meaning: str | None
    missing_count: int
    excluded_count: int
    deduplication_policy: str


class DocumentPage(_Out):
    items: list[DocumentOut]
    pagination: PageMeta
    applied_filters: dict[str, Any]
    access: AccessNotice
    empty_result_message: str | None = None


class FieldCoverage(_Out):
    field: str
    present: int
    missing: int


class SourceQuality(_Out):
    source_id: str
    record_level: str
    rows: int
    fields: list[FieldCoverage]
    top_warnings: dict[str, int]
    meta: MeasureMeta


class DataQualityResponse(_Out):
    sources: list[SourceQuality]
    access: AccessNotice


class FlowCompleteness(_Out):
    source_id: str
    flow_kind: str
    observations: int
    reported: int
    not_reported: int
    unparseable: int
    invalid: int
    reported_without_currency: int
    reported_without_unit: int
    component_lines: int
    meta: MeasureMeta


class FinancingCompletenessResponse(_Out):
    flows: list[FlowCompleteness]
    access: AccessNotice


class TimelinePoint(_Out):
    year: int
    projects_approved: int
    by_current_status: dict[str, int]
    gcf_funding: TrendPoint | None


class GcfTimelineResponse(_Out):
    country: str | None
    points: list[TimelinePoint]
    projects_without_approval_date: int
    projects_meta: MeasureMeta
    funding_meta: MeasureMeta
    disclaimers: list[str]
    access: AccessNotice


class CountryAggregateOut(_Out):
    iso3: str
    country_name: str
    region: str | None
    measure: str
    measure_label: str
    value_kind: str
    amount: Decimal | None
    value_status: str
    currency: str | None
    unit: str | None
    snapshot_date: date | None
    meta: MeasureMeta


class CountryAggregatesResponse(_Out):
    items: list[CountryAggregateOut]
    rule: str
    access: AccessNotice


class RelationshipSummaryRow(_Out):
    relation_type: str
    table: str
    verification_state: str
    status: str | None
    links: int
    asserted_by_source_id: str | None


class RelationshipSummaryResponse(_Out):
    rows: list[RelationshipSummaryRow]
    policy: list[str]
    access: AccessNotice
