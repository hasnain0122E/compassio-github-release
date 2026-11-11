"""SQLAlchemy 2.x ORM entities (docs/architecture/database_design.md).

Units of observation are never merged: a project row is one record *as its source publishes it*
(an AidData record, a GCF funded project, a CFU project row, an ADB financing instrument).
Cross-source identity lives only in ``project_relationships`` with method and status.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from compassio_api.db.types import DecimalText

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

FLOW_KINDS = (
    "approval",
    "commitment",
    "pledge",
    "deposit",
    "disbursement",
    "repayment_principal",
    "repayment_interest",
    "gcf_financing",
    "co_financing",
    "total_project_cost",
    "readiness_grant",
)
LEVELS = ("project", "financing_instrument", "transaction", "country_aggregate", "fund_aggregate")
VALUE_STATUSES = ("reported", "not_reported", "unparseable", "invalid")
UNIT_STATUSES = ("stated_in_source", "declared_default_currency", "not_stated_in_source")
PRICE_BASES = ("nominal", "constant_2021_usd", "unspecified")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Source(Base):
    """A registered raw source (copied from data/manifests/source_manifest.json)."""

    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(Text)
    version_info: Mapped[str | None] = mapped_column(Text)
    file_relpath: Mapped[str] = mapped_column(Text)
    file_sha256: Mapped[str] = mapped_column(String(64))
    reference_url: Mapped[str | None] = mapped_column(Text)
    rights_status: Mapped[str] = mapped_column(String(40))
    rights_evidence: Mapped[str | None] = mapped_column(Text)
    license_notes: Mapped[str | None] = mapped_column(Text)
    observation_type: Mapped[str] = mapped_column(Text)
    audited_record_count: Mapped[int | None] = mapped_column(Integer)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # canonical = data/manifests/source_manifest.json; backend_staging = backend registry.
    source_registry: Mapped[str] = mapped_column(String(30), server_default="canonical")
    # restricted_internal sources are never served by the API, in any mode.
    access_tier: Mapped[str] = mapped_column(String(30), server_default="standard")

    __table_args__ = (
        CheckConstraint("length(file_sha256) = 64", name="sha256_length"),
        CheckConstraint(
            _in("source_registry", ("canonical", "backend_staging")), name="source_registry"
        ),
        CheckConstraint(
            _in("access_tier", ("standard", "restricted_internal")), name="access_tier"
        ),
    )


class ImportRun(Base):
    """One execution of `compassio-db ingest` for one source key."""

    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str] = mapped_column(String(80))
    input_sha256: Mapped[dict[str, Any]] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    removed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(_in("status", ("running", "completed", "failed")), name="status"),
    )


class Project(Base):
    __tablename__ = "projects"

    # "<source_id>:<source_project_id>" -- stable, namespaced by source.
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    source_project_id: Mapped[str] = mapped_column(String(200))
    record_level: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    recipient_label: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    # True = the record is not attributable to exactly one country (multi-country or regional).
    multi_country: Mapped[bool] = mapped_column(Boolean)
    sector_name: Mapped[str | None] = mapped_column(String(200))
    sector_code: Mapped[str | None] = mapped_column(String(40))
    sector_vocabulary: Mapped[str | None] = mapped_column(String(60))
    year: Mapped[int | None] = mapped_column(Integer)
    year_type: Mapped[str | None] = mapped_column(String(60))
    date_value: Mapped[date | None] = mapped_column(Date)
    date_precision: Mapped[str | None] = mapped_column(String(10))
    date_estimated: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str | None] = mapped_column(String(80))
    group_key: Mapped[str | None] = mapped_column(String(200))
    group_meaning: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64))
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))

    countries: Mapped[list["ProjectCountry"]] = relationship(
        back_populates="project", order_by="ProjectCountry.position", lazy="raise"
    )
    annotations: Mapped[list["ClimateAnnotation"]] = relationship(
        back_populates="project", order_by="ClimateAnnotation.scheme", lazy="raise"
    )
    observations: Mapped[list["FinancialObservation"]] = relationship(
        back_populates="project", order_by="FinancialObservation.id", lazy="raise"
    )
    warnings: Mapped[list["DataQualityWarning"]] = relationship(
        back_populates="project", order_by="DataQualityWarning.code", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("source_id", "source_project_id", name="uq_projects_source_record"),
        CheckConstraint("length(title) > 0", name="title_not_empty"),
        CheckConstraint(_in("date_precision", ("day", "year")), name="date_precision"),
        CheckConstraint("year IS NULL OR (year BETWEEN 1900 AND 2100)", name="year_range"),
        Index("ix_projects_source_year", "source_id", "year"),
        Index("ix_projects_year", "year"),
        Index("ix_projects_sector_name", "sector_name"),
        Index("ix_projects_group_key", "group_key"),
    )


class ProjectCountry(Base):
    __tablename__ = "project_countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    country_name: Mapped[str] = mapped_column(Text)  # as published
    iso3: Mapped[str | None] = mapped_column(String(3))  # None = not mappable (regional etc.)
    mapping_method: Mapped[str] = mapped_column(String(80))

    project: Mapped[Project] = relationship(back_populates="countries")

    __table_args__ = (
        UniqueConstraint("project_id", "position", name="uq_project_countries_position"),
        CheckConstraint("iso3 IS NULL OR length(iso3) = 3", name="iso3_length"),
        Index("ix_project_countries_iso3_project", "iso3", "project_id"),
        Index("ix_project_countries_project", "project_id"),
    )


class ClimateAnnotation(Base):
    """A climate classification published by a source. Never a Compassio model prediction."""

    __tablename__ = "climate_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    annotation_source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    scheme: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(40))
    is_model_prediction: Mapped[bool] = mapped_column(Boolean, default=False)
    overall: Mapped[int | None] = mapped_column(Integer)
    mitigation: Mapped[int | None] = mapped_column(Integer)
    adaptation: Mapped[int | None] = mapped_column(Integer)
    is_climate_related: Mapped[bool | None] = mapped_column(Boolean)
    label: Mapped[str | None] = mapped_column(Text)
    raw_value: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="annotations")

    __table_args__ = (
        UniqueConstraint("project_id", "scheme", name="uq_climate_annotations_scheme"),
        CheckConstraint("is_model_prediction = false", name="not_model_prediction"),
        CheckConstraint(_in("kind", ("research_annotation", "source_classification")), name="kind"),
        Index(
            "ix_climate_annotations_scheme_flag_project",
            "scheme",
            "is_climate_related",
            "project_id",
        ),
        Index("ix_climate_annotations_project", "project_id"),
    )


class FinancialObservation(Base):
    """One published amount with its meaning. Missing = NULL amount, never zero."""

    __tablename__ = "financial_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    observation_key: Mapped[str] = mapped_column(String(240))
    flow_kind: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(40))
    financing_type: Mapped[str | None] = mapped_column(String(80))
    is_component: Mapped[bool] = mapped_column(Boolean)  # part of another stated total
    amount: Mapped[Decimal | None] = mapped_column(DecimalText())
    raw_value: Mapped[str | None] = mapped_column(Text)
    value_status: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str | None] = mapped_column(String(3))
    unit_status: Mapped[str] = mapped_column(String(40))
    price_basis: Mapped[str] = mapped_column(String(30))
    effective_date: Mapped[date | None] = mapped_column(Date)
    effective_year: Mapped[int | None] = mapped_column(Integer)
    date_meaning: Mapped[str] = mapped_column(Text)
    multi_country: Mapped[bool] = mapped_column(Boolean)
    estimated: Mapped[bool | None] = mapped_column(Boolean)
    recommended_for_aggregates: Mapped[bool | None] = mapped_column(Boolean)
    source_reference: Mapped[str] = mapped_column(Text)
    # Set only when the SOURCE publishes a per-country breakdown (e.g. GCF API country lines);
    # never derived by Compassio.
    country_iso3: Mapped[str | None] = mapped_column(String(3))

    project: Mapped[Project] = relationship(back_populates="observations")

    __table_args__ = (
        UniqueConstraint("source_id", "observation_key", name="uq_financial_observations_key"),
        CheckConstraint(_in("flow_kind", FLOW_KINDS), name="flow_kind"),
        CheckConstraint(_in("level", LEVELS), name="level"),
        CheckConstraint(_in("value_status", VALUE_STATUSES), name="value_status"),
        CheckConstraint(_in("unit_status", UNIT_STATUSES), name="unit_status"),
        CheckConstraint(_in("price_basis", PRICE_BASES), name="price_basis"),
        CheckConstraint(
            "(value_status = 'reported') = (amount IS NOT NULL)", name="amount_iff_reported"
        ),
        CheckConstraint("unit IS NULL OR unit IN ('units', 'thousands', 'millions')", name="unit"),
        CheckConstraint("currency IS NULL OR length(currency) = 3", name="currency_length"),
        CheckConstraint(
            "price_basis != 'constant_2021_usd' OR currency = 'USD'", name="constant_usd"
        ),
        Index("ix_financial_observations_metric", "source_id", "flow_kind", "effective_year"),
        Index("ix_financial_observations_project", "project_id"),
    )


class ProjectRelationship(Base):
    """Explicit, evidence-based link between two project rows. Never an implicit merge."""

    __tablename__ = "project_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    to_project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    asserted_by_source_id: Mapped[str | None] = mapped_column(String(80))
    verification_state: Mapped[str] = mapped_column(
        String(60), server_default="candidate_requires_review"
    )
    last_verified_on: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint(
            "from_project_id", "to_project_id", "relation_type", name="uq_project_relationships"
        ),
        CheckConstraint("from_project_id != to_project_id", name="not_self"),
        CheckConstraint(
            _in(
                "status",
                (
                    "same_record_stable_id",
                    "probable_match_reference_code",
                    "possible_match_requires_review",
                    "related_not_same",
                ),
            ),
            name="status",
        ),
        Index("ix_project_relationships_to", "to_project_id"),
    )


class DataQualityWarning(Base):
    __tablename__ = "data_quality_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(80))
    field: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="warnings")

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_data_quality_warnings_code"),
        Index("ix_data_quality_warnings_code", "code"),
    )


VERIFICATION_STATES = (
    "deterministic_identifier_match",
    "deterministic_identifier_structure",
    "candidate_requires_review",
    "human_verified",
)


class ProjectEnrichment(Base):
    """Values for an existing project published by ANOTHER record of the same publisher (e.g.
    the GCF API for a GCF export row). Both values are preserved; nothing is overwritten."""

    __tablename__ = "project_enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    snapshot_id: Mapped[str] = mapped_column(String(40))
    source_record_id: Mapped[str] = mapped_column(String(120))
    relation_type: Mapped[str] = mapped_column(String(60))
    match_method: Mapped[str] = mapped_column(Text)
    match_evidence: Mapped[str] = mapped_column(Text)
    verification_state: Mapped[str] = mapped_column(String(60))
    review_status: Mapped[str] = mapped_column(String(40))
    last_verified_on: Mapped[date] = mapped_column(Date)
    official_url: Mapped[str | None] = mapped_column(Text)
    approval_date: Mapped[date | None] = mapped_column(Date)
    approval_date_type: Mapped[str | None] = mapped_column(String(80))
    approval_status: Mapped[str | None] = mapped_column(String(80))
    project_status: Mapped[str | None] = mapped_column(String(80))
    status_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_as_of_meaning: Mapped[str | None] = mapped_column(Text)
    values: Mapped[dict[str, Any]] = mapped_column(JSON)  # as published, field by field
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("project_id", "source_id", name="uq_project_enrichments_source"),
        CheckConstraint(_in("verification_state", VERIFICATION_STATES), name="verification"),
        Index("ix_project_enrichments_source_record", "source_id", "source_record_id"),
    )


class Document(Base):
    """A document as listed by a document catalogue (never an independent project)."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(300), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    source_document_id: Mapped[str] = mapped_column(String(280))
    family_id: Mapped[str | None] = mapped_column(String(280))
    family_name: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str | None] = mapped_column(String(120))
    publisher_fund: Mapped[str | None] = mapped_column(String(40))
    document_date: Mapped[date | None] = mapped_column(Date)
    document_date_type: Mapped[str | None] = mapped_column(String(120))
    geographies: Mapped[list[str]] = mapped_column(JSON)
    languages: Mapped[str | None] = mapped_column(Text)
    catalogue_url: Mapped[str | None] = mapped_column(Text)
    content_url: Mapped[str | None] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_sha256: Mapped[str] = mapped_column(String(64))
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))

    __table_args__ = (
        UniqueConstraint("source_id", "source_document_id", name="uq_documents_source_doc"),
        Index("ix_documents_family", "family_id"),
    )


class DocumentLink(Base):
    __tablename__ = "document_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(60))
    match_method: Mapped[str] = mapped_column(Text)
    match_evidence: Mapped[str] = mapped_column(Text)
    asserted_by_source_id: Mapped[str] = mapped_column(String(80))
    verification_state: Mapped[str] = mapped_column(String(60))
    review_status: Mapped[str] = mapped_column(String(40))
    last_verified_on: Mapped[date] = mapped_column(Date)

    __table_args__ = (
        UniqueConstraint("document_id", "project_id", name="uq_document_links_pair"),
        CheckConstraint(_in("verification_state", VERIFICATION_STATES), name="verification"),
        Index("ix_document_links_project", "project_id"),
    )


class RecordGroup(Base):
    """Explicit parent grouping (ADB project number, AidData parent package) with evidence."""

    __tablename__ = "record_groups"

    group_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    group_type: Mapped[str] = mapped_column(String(60))
    member_relation_type: Mapped[str] = mapped_column(String(60))
    match_method: Mapped[str] = mapped_column(Text)
    verification_state: Mapped[str] = mapped_column(String(60))
    review_status: Mapped[str] = mapped_column(String(40))
    last_verified_on: Mapped[date] = mapped_column(Date)
    member_count: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(_in("verification_state", VERIFICATION_STATES), name="verification"),
    )


class CountryAggregate(Base):
    """A source-published country-level figure. Never added to project-level observations."""

    __tablename__ = "country_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    iso3: Mapped[str] = mapped_column(String(3))
    country_name: Mapped[str] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    measure: Mapped[str] = mapped_column(String(60))
    measure_label: Mapped[str] = mapped_column(Text)
    value_kind: Mapped[str] = mapped_column(String(10))  # money | count
    amount: Mapped[Decimal | None] = mapped_column(DecimalText())
    raw_value: Mapped[str | None] = mapped_column(Text)
    value_status: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str | None] = mapped_column(String(3))
    unit_status: Mapped[str] = mapped_column(String(40))
    snapshot_date: Mapped[date | None] = mapped_column(Date)
    date_meaning: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))

    __table_args__ = (
        UniqueConstraint("source_id", "iso3", "measure", name="uq_country_aggregates_measure"),
        CheckConstraint(_in("value_kind", ("money", "count")), name="value_kind"),
        CheckConstraint(_in("value_status", VALUE_STATUSES), name="value_status"),
        CheckConstraint(
            "(value_status = 'reported') = (amount IS NOT NULL)", name="amount_iff_reported"
        ),
        Index("ix_country_aggregates_iso3", "iso3"),
    )


class HistoricalStagingRecord(Base):
    """GCF historical archive rows: provenance unverified, so restricted internal staging only.
    Never served by the API, never treated as compatible with the modern export."""

    __tablename__ = "historical_staging"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.source_id"))
    source_record_id: Mapped[str] = mapped_column(String(80))
    theme: Mapped[str | None] = mapped_column(String(60))
    accredited_entity: Mapped[str | None] = mapped_column(Text)
    total_financing_raw: Mapped[str | None] = mapped_column(Text)
    total_financing: Mapped[Decimal | None] = mapped_column(DecimalText())
    value_status: Mapped[str] = mapped_column(String(20))
    unit: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3))
    unit_status: Mapped[str] = mapped_column(String(40))
    matched_project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id"))

    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_historical_staging_record"),
        CheckConstraint(_in("value_status", VALUE_STATUSES), name="value_status"),
    )
