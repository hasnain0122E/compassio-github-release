"""Database integrity verification against the audited source facts.

Expected values are copied from committed audit documents (references inline), not tuned to the
database. A mismatch fails ``compassio-db verify``.
"""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    ClimateAnnotation,
    CountryAggregate,
    DataQualityWarning,
    Document,
    DocumentLink,
    FinancialObservation,
    HistoricalStagingRecord,
    ImportRun,
    Project,
    ProjectCountry,
    ProjectEnrichment,
    ProjectRelationship,
    Source,
)
from compassio_api.services.access import PERMITTED_RIGHTS

# Each expectation: (value, reference)
EXPECTED: dict[str, tuple[int, str]] = {
    "aiddata.projects": (20_985, "data_quality_audit.md; research_label_audit.md"),
    "aiddata.rio_annotations": (20_985, "research_label_audit.md"),
    "aiddata.climate_related": (1_383, "research_label_audit.md (rio overall > 0)"),
    "aiddata.pakistan_records": (496, "pakistan_coverage.md"),
    "aiddata.pakistan_climate_related": (76, "pakistan_coverage.md"),
    "aiddata.amount_reported_records": (12_799, "financial_fields_audit.md §1"),
    "aiddata.amount_not_reported_records": (8_186, "financial_fields_audit.md §5"),
    "aiddata.not_recommended_for_aggregates": (3_028, "cross_source_overlap.md §2"),
    "gcf_projects.projects": (379, "cross_source_overlap.md §4"),
    "gcf_projects.multi_country": (96, "financial_fields_audit.md §5"),
    "gcf_projects.pakistan_projects": (11, "financial_fields_audit.md §2.4 (8 single + 3 multi)"),
    "gcf_projects.pakistan_single_country": (8, "financial_fields_audit.md §2.4"),
    "climate_funds_update.projects": (4_066, "financial_fields_audit.md §1"),
    "climate_funds_update.gcf_reference_links": (329, "cross_source_overlap.md §4"),
    "adb_pakistan.instruments": (193, "cross_source_overlap.md §6"),
    "adb_pakistan.project_numbers": (143, "cross_source_overlap.md §6"),
    "adb_pakistan.commitment_transactions": (192, "financial_fields_audit.md §1 (type 2)"),
    "adb_pakistan.disbursement_transactions": (7_117, "financial_fields_audit.md §1 (type 3)"),
    "adb_pakistan.interest_transactions": (14_062, "financial_fields_audit.md §1 (type 5)"),
    "adb_pakistan.principal_transactions": (9_591, "financial_fields_audit.md §1 (type 6)"),
}
# Task 006-DB sources; checked only once the source has been ingested.
EXPECTED_EXTENDED: dict[str, tuple[int, str]] = {
    "gcf_readiness.rows": (876, "financial_fields_audit.md §1 (readiness 'Financing' rows)"),
    "gcf_countries.countries": (155, "financial_fields_audit.md §1 (GCF countries)"),
    "climate_project_explorer.documents": (818, "cross_source_overlap.md §5 (CPE rows)"),
    "climate_project_explorer.families": (498, "cross_source_overlap.md §5 (CPE families)"),
    "climate_project_explorer.gcf_projects_linked": (
        121,
        "cross_source_overlap.md §5 (121 GCF links via reference codes)",
    ),
    "gcf_historical.rows": (128, "cross_source_overlap.md §3"),
    "gcf_historical.matched_to_export": (123, "cross_source_overlap.md §3"),
}


def table_counts(session: Session) -> dict[str, int]:
    out: dict[str, int] = {}
    for model in (
        Source,
        ProjectEnrichment,
        Document,
        DocumentLink,
        CountryAggregate,
        HistoricalStagingRecord,
        Project,
        ProjectCountry,
        ClimateAnnotation,
        FinancialObservation,
        ProjectRelationship,
        DataQualityWarning,
        ImportRun,
    ):
        out[model.__tablename__] = int(session.scalar(select(func.count()).select_from(model)) or 0)
    return out


def _count(session: Session, stmt: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def _projects(source: str) -> Any:
    return select(Project.id).where(Project.source_id == source)


def _pakistan(source: str) -> Any:
    return (
        select(Project.id)
        .where(Project.source_id == source)
        .where(
            Project.id.in_(select(ProjectCountry.project_id).where(ProjectCountry.iso3 == "PAK"))
        )
    )


def _obs(source: str, **filters: Any) -> Any:
    stmt = select(FinancialObservation.id).where(FinancialObservation.source_id == source)
    for column, value in filters.items():
        stmt = stmt.where(getattr(FinancialObservation, column) == value)
    return stmt


def observed_values(session: Session) -> dict[str, int]:
    rio = select(ClimateAnnotation.project_id).where(
        ClimateAnnotation.scheme == "rio_marker_qi_et_al_2026"
    )
    pk_ids = select(ProjectCountry.project_id).where(ProjectCountry.iso3 == "PAK")
    gcf_links = select(ProjectRelationship.id).where(
        ProjectRelationship.relation_type == "cross_source_reference_code"
    )
    return {
        "aiddata.projects": _count(session, _projects("aiddata")),
        "aiddata.rio_annotations": _count(session, rio),
        "aiddata.climate_related": _count(
            session, rio.where(ClimateAnnotation.is_climate_related.is_(True))
        ),
        "aiddata.pakistan_records": _count(session, _pakistan("aiddata")),
        "aiddata.pakistan_climate_related": _count(
            session,
            rio.where(ClimateAnnotation.is_climate_related.is_(True)).where(
                ClimateAnnotation.project_id.in_(pk_ids)
            ),
        ),
        "aiddata.amount_reported_records": _count(
            session,
            _obs("aiddata", value_status="reported").where(
                FinancialObservation.observation_key.like("%:amount_original_currency")
            ),
        ),
        "aiddata.amount_not_reported_records": _count(
            session,
            _obs("aiddata", value_status="not_reported").where(
                FinancialObservation.observation_key.like("%:amount_original_currency")
            ),
        ),
        "aiddata.not_recommended_for_aggregates": _count(
            session,
            select(DataQualityWarning.id).where(
                DataQualityWarning.code == "not_recommended_for_aggregates"
            ),
        ),
        "gcf_projects.projects": _count(session, _projects("gcf_projects")),
        "gcf_projects.multi_country": _count(
            session, _projects("gcf_projects").where(Project.multi_country)
        ),
        "gcf_projects.pakistan_projects": _count(session, _pakistan("gcf_projects")),
        "gcf_projects.pakistan_single_country": _count(
            session, _pakistan("gcf_projects").where(Project.multi_country.is_(False))
        ),
        "climate_funds_update.projects": _count(session, _projects("climate_funds_update")),
        "climate_funds_update.gcf_reference_links": _count(session, gcf_links),
        "adb_pakistan.instruments": _count(session, _projects("adb_pakistan")),
        "adb_pakistan.project_numbers": int(
            session.scalar(
                select(func.count(func.distinct(Project.group_key))).where(
                    Project.source_id == "adb_pakistan"
                )
            )
            or 0
        ),
        "adb_pakistan.commitment_transactions": _count(
            session, _obs("adb_pakistan", flow_kind="commitment")
        ),
        "adb_pakistan.disbursement_transactions": _count(
            session, _obs("adb_pakistan", flow_kind="disbursement")
        ),
        "adb_pakistan.interest_transactions": _count(
            session, _obs("adb_pakistan", flow_kind="repayment_interest")
        ),
        "adb_pakistan.principal_transactions": _count(
            session, _obs("adb_pakistan", flow_kind="repayment_principal")
        ),
    }


def observed_extended(session: Session) -> dict[str, int | None]:
    def ingested(model: Any) -> bool:
        return bool(session.scalar(select(func.count()).select_from(model)))

    out: dict[str, int | None] = dict.fromkeys(EXPECTED_EXTENDED)
    if _count(session, _projects("gcf_readiness")):
        out["gcf_readiness.rows"] = _count(session, _projects("gcf_readiness"))
    if ingested(CountryAggregate):
        out["gcf_countries.countries"] = int(
            session.scalar(select(func.count(func.distinct(CountryAggregate.iso3)))) or 0
        )
    if ingested(Document):
        out["climate_project_explorer.documents"] = _count(session, select(Document.id))
        out["climate_project_explorer.families"] = int(
            session.scalar(select(func.count(func.distinct(Document.family_id)))) or 0
        )
        out["climate_project_explorer.gcf_projects_linked"] = int(
            session.scalar(select(func.count(func.distinct(DocumentLink.project_id)))) or 0
        )
    if ingested(HistoricalStagingRecord):
        out["gcf_historical.rows"] = _count(session, select(HistoricalStagingRecord.id))
        out["gcf_historical.matched_to_export"] = _count(
            session,
            select(HistoricalStagingRecord.id).where(
                HistoricalStagingRecord.matched_project_id.is_not(None)
            ),
        )
    return out


def structural_checks(session: Session) -> dict[str, Any]:
    dup_source_ids = _count(
        session,
        select(Project.source_id, Project.source_project_id)
        .group_by(Project.source_id, Project.source_project_id)
        .having(func.count() > 1),
    )
    dup_obs = _count(
        session,
        select(FinancialObservation.source_id, FinancialObservation.observation_key)
        .group_by(FinancialObservation.source_id, FinancialObservation.observation_key)
        .having(func.count() > 1),
    )
    gcf_multi_linked = _count(
        session,
        select(ProjectRelationship.to_project_id)
        .where(ProjectRelationship.relation_type == "cross_source_reference_code")
        .group_by(ProjectRelationship.to_project_id)
        .having(func.count() > 1),
    )
    converted = _count(
        session,
        select(FinancialObservation.id)
        .where(FinancialObservation.price_basis == "constant_2021_usd")
        .where(FinancialObservation.source_id != "aiddata"),
    )
    gcf_currency_assumed = _count(
        session,
        _obs("gcf_projects").where(FinancialObservation.currency.is_not(None)),
    )
    reported_without_amount = _count(
        session,
        select(FinancialObservation.id)
        .where(FinancialObservation.value_status == "reported")
        .where(FinancialObservation.amount.is_(None)),
    )
    sources = session.scalars(select(Source)).all()
    cleared = sorted(s.source_id for s in sources if s.rights_status in PERMITTED_RIGHTS)
    backend_not_unreviewed = sorted(
        s.source_id
        for s in sources
        if s.source_registry == "backend_staging" and s.rights_status != "not_reviewed"
    )
    enrichment_dupes = _count(
        session,
        select(ProjectEnrichment.project_id, ProjectEnrichment.source_id)
        .group_by(ProjectEnrichment.project_id, ProjectEnrichment.source_id)
        .having(func.count() > 1),
    )
    api_totals_with_currency = _count(
        session,
        select(FinancialObservation.id).where(
            FinancialObservation.source_id == "gcf_api_projects",
            FinancialObservation.is_component.is_(False),
            FinancialObservation.level == "project",
            FinancialObservation.currency.is_not(None),
        ),
    )
    restricted = sorted(s.source_id for s in sources if s.access_tier == "restricted_internal")
    checks = {
        "duplicate_source_project_ids": dup_source_ids,
        "duplicate_observation_keys": dup_obs,
        "gcf_projects_linked_from_more_than_one_cfu_row": gcf_multi_linked,
        "non_aiddata_constant_usd_observations": converted,
        "gcf_observations_with_assumed_currency": gcf_currency_assumed,
        "reported_observations_without_amount": reported_without_amount,
        "sources_registered": len(sources),
        "sources_cleared_for_public_display": cleared,
        "backend_sources_not_unreviewed": backend_not_unreviewed,
        "duplicate_enrichments_per_project": enrichment_dupes,
        "gcf_api_project_totals_with_assumed_currency": api_totals_with_currency,
        "restricted_internal_sources": restricted,
    }
    checks["ok"] = (
        dup_source_ids == 0
        and dup_obs == 0
        and gcf_multi_linked == 0
        and converted == 0
        and gcf_currency_assumed == 0
        and reported_without_amount == 0
        and not cleared
        and not backend_not_unreviewed
        and enrichment_dupes == 0
        and api_totals_with_currency == 0
    )
    return checks


def verify_database(session: Session) -> dict[str, Any]:
    observed = observed_values(session)
    comparisons = {
        key: {
            "expected": expected,
            "observed": observed[key],
            "match": expected == observed[key],
            "reference": reference,
        }
        for key, (expected, reference) in EXPECTED.items()
    }
    extended = observed_extended(session)
    for key, (expected, reference) in EXPECTED_EXTENDED.items():
        value = extended[key]
        comparisons[key] = {
            "expected": expected,
            "observed": value,
            "match": True if value is None else expected == value,
            "reference": reference + ("" if value is not None else " (source not ingested)"),
        }
    structure = structural_checks(session)
    return {
        "ok": all(c["match"] for c in comparisons.values()) and bool(structure["ok"]),
        "counts": table_counts(session),
        "audited_comparisons": comparisons,
        "structural_checks": structure,
    }
