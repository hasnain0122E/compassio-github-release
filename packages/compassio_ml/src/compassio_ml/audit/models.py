"""Typed result records produced by the data audit. All values are observations
computed from files on disk; nothing here is hand-entered."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class _Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IssueCategory(StrEnum):
    PROVENANCE = "provenance"
    SCHEMA = "schema"
    MISSING_VALUES = "missing_values"
    DUPLICATES = "duplicates"
    UNIT_OF_OBSERVATION = "unit_of_observation"
    LABEL = "label"
    LEAKAGE = "leakage"
    FINANCIAL = "financial"
    DATE = "date"
    TEXT = "text"


class QualityIssue(_Row):
    source_id: str
    issue_id: str
    severity: Severity
    category: IssueCategory
    field: str
    affected_records: int
    description: str
    recommendation: str


class ColumnProfile(_Row):
    name: str
    non_blank: int
    blank: int
    distinct: int


class TableSchema(_Row):
    source_id: str
    table: str
    unit_of_observation: str
    row_count: int
    columns: tuple[ColumnProfile, ...]


class CoverageRow(_Row):
    source_id: str
    table: str
    unit_of_observation: str
    record_count: int
    distinct_id_count: int | None
    duplicate_id_rows: int | None
    title_present: int | None
    description_present: int | None
    amount_present: int | None
    date_field: str
    date_meaning: str
    earliest: str | None
    latest: str | None
    pakistan_records: int | None
    records_dated_2026: int | None
    notes: str


class PakistanRow(_Row):
    source_id: str
    table: str
    unit_of_observation: str
    filter_rule: str
    records: int
    climate_flagged: int | None
    notes: str


class LabelRow(_Row):
    label_field: str
    value: str
    records: int
    share: float
    pakistan_records: int
    meaning: str


class FinancialField(_Row):
    source_id: str
    table: str
    field: str
    flow_kind: str
    level: str
    unit: str
    currency: str
    non_blank: int
    parse_failures: int
    notes: str


class OverlapRow(_Row):
    left_source: str
    left_key: str
    right_source: str
    right_key: str
    match_method: str
    status: str
    evidence: str


class Year2026Row(_Row):
    source_id: str
    table: str
    date_field: str
    date_meaning: str
    records: int | None  # None = cannot be determined from the file
    notes: str
