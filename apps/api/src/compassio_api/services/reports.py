"""Offline coverage and reconciliation reports (CLI: ``compassio-db report <name>``).

Every number is computed from the database at run time; nothing is hard-coded except the
audited expectations quoted with their document reference (``services.integrity``).
"""

import json
from collections import Counter
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    CountryAggregate,
    Document,
    DocumentLink,
    FinancialObservation,
    HistoricalStagingRecord,
    ImportRun,
    Project,
    ProjectCountry,
    ProjectEnrichment,
    ProjectRelationship,
    RecordGroup,
)

API_SOURCE = "gcf_api_projects"


def _latest_run_result(session: Session, source_key: str) -> dict[str, Any]:
    run = session.scalar(
        select(ImportRun)
        .where(ImportRun.source_key == source_key, ImportRun.status == "completed")
        .order_by(ImportRun.id.desc())
    )
    if run is None or not run.message:
        return {}
    try:
        data = json.loads(run.message)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _verified_finance_projects(session: Session) -> set[str]:
    return set(
        session.scalars(
            select(FinancialObservation.project_id)
            .where(
                FinancialObservation.source_id == API_SOURCE,
                FinancialObservation.flow_kind == "gcf_financing",
                FinancialObservation.value_status == "reported",
                FinancialObservation.currency.is_not(None),
            )
            .distinct()
        ).all()
    )


def gcf_enrichment_report(session: Session) -> dict[str, Any]:
    export_ids = set(
        session.scalars(select(Project.id).where(Project.source_id == "gcf_projects")).all()
    )
    enrichments = session.scalars(
        select(ProjectEnrichment).where(ProjectEnrichment.source_id == API_SOURCE)
    ).all()
    matched = {e.project_id for e in enrichments}
    verified_finance = _verified_finance_projects(session)
    conflict_fields: Counter[str] = Counter()
    for e in enrichments:
        for c in e.conflicts:
            conflict_fields[str(c.get("field"))] += 1
    run = _latest_run_result(session, API_SOURCE)
    pk_ids = set(
        session.scalars(
            select(ProjectCountry.project_id).where(
                ProjectCountry.iso3 == "PAK",
                ProjectCountry.project_id.in_(export_ids),
            )
        ).all()
    )
    by_id = {e.project_id: e for e in enrichments}
    pk_country_lines = dict(
        session.execute(
            select(FinancialObservation.project_id, func.count())
            .where(
                FinancialObservation.source_id == API_SOURCE,
                FinancialObservation.financing_type == "country_breakdown",
                FinancialObservation.flow_kind == "gcf_financing",
                FinancialObservation.country_iso3 == "PAK",
                FinancialObservation.value_status == "reported",
            )
            .group_by(FinancialObservation.project_id)
        ).all()
    )
    pakistan = []
    for project_id in sorted(pk_ids):
        enr = by_id.get(project_id)
        pakistan.append(
            {
                "project_id": project_id,
                "matched": enr is not None,
                "approval_date": enr.approval_date.isoformat()
                if enr and enr.approval_date
                else None,
                "status": enr.project_status if enr else None,
                "official_url": bool(enr and enr.official_url),
                "currency_verified_gcf_financing": project_id in verified_finance,
                "gcf_published_pakistan_breakdown_lines": int(pk_country_lines.get(project_id, 0)),
                "conflicts": sorted(str(c.get("field")) for c in enr.conflicts) if enr else [],
            }
        )
    return {
        "snapshot_id": run.get("snapshot_id"),
        "export_projects": len(export_ids),
        "api_records": run.get("api_records"),
        "matched_export_projects": len(matched),
        "export_projects_without_api_record": sorted(
            p.split(":", 1)[1] for p in export_ids - matched
        ),
        "api_records_not_in_export": run.get("api_records_not_in_export", []),
        "with_verified_approval_date": sum(1 for e in enrichments if e.approval_date),
        "with_status": sum(1 for e in enrichments if e.project_status),
        "status_values": dict(Counter(e.project_status or "none" for e in enrichments)),
        "with_currency_verified_gcf_financing": len(verified_finance & matched),
        "with_official_url": sum(1 for e in enrichments if e.official_url),
        "with_any_conflict": sum(1 for e in enrichments if e.conflicts),
        "conflicts_by_field": dict(conflict_fields),
        "proposal_document_urls_collected": 0,
        "proposal_document_note": (
            "The API publishes no document URLs; project pages were not scraped. Document links "
            "come only from Climate Project Explorer metadata (document_links)."
        ),
        "pakistan": {
            "export_projects_listing_pakistan": len(pk_ids),
            "matched": sum(1 for r in pakistan if r["matched"]),
            "with_approval_date": sum(1 for r in pakistan if r["approval_date"]),
            "with_status": sum(1 for r in pakistan if r["status"]),
            "with_currency_verified_gcf_financing": sum(
                1 for r in pakistan if r["currency_verified_gcf_financing"]
            ),
            "with_gcf_published_pakistan_breakdown": sum(
                1 for r in pakistan if r["gcf_published_pakistan_breakdown_lines"]
            ),
            "projects": pakistan,
        },
    }


def _count(session: Session, stmt: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def reconciliation_report(session: Session) -> dict[str, Any]:
    projects = dict(
        session.execute(select(Project.source_id, func.count()).group_by(Project.source_id)).all()
    )
    observations = {
        f"{s}|{k}": int(n)
        for s, k, n in session.execute(
            select(
                FinancialObservation.source_id, FinancialObservation.flow_kind, func.count()
            ).group_by(FinancialObservation.source_id, FinancialObservation.flow_kind)
        ).all()
    }
    duplicate_keys = _count(
        session,
        select(FinancialObservation.source_id, FinancialObservation.observation_key)
        .group_by(FinancialObservation.source_id, FinancialObservation.observation_key)
        .having(func.count() > 1),
    )
    api_on_non_gcf = _count(
        session,
        select(FinancialObservation.id)
        .join(Project, Project.id == FinancialObservation.project_id)
        .where(FinancialObservation.source_id == API_SOURCE, Project.source_id != "gcf_projects"),
    )
    api_totals_with_currency = _count(
        session,
        select(FinancialObservation.id).where(
            FinancialObservation.source_id == API_SOURCE,
            FinancialObservation.is_component.is_(False),
            FinancialObservation.level == "project",
            FinancialObservation.currency.is_not(None),
        ),
    )
    enrichment_duplicates = _count(
        session,
        select(ProjectEnrichment.project_id, ProjectEnrichment.source_id)
        .group_by(ProjectEnrichment.project_id, ProjectEnrichment.source_id)
        .having(func.count() > 1),
    )
    # GCF funding lines (USD only) vs published TotalGCFFunding, per project, as a consistency
    # check of the API itself -- informative, never used to replace a value.
    usd_lines: dict[str, Decimal] = {}
    non_usd: set[str] = set()
    for project_id, amount, currency in session.execute(
        select(
            FinancialObservation.project_id,
            FinancialObservation.amount,
            FinancialObservation.currency,
        ).where(
            FinancialObservation.source_id == API_SOURCE,
            FinancialObservation.flow_kind == "gcf_financing",
            FinancialObservation.is_component.is_(True),
            FinancialObservation.financing_type != "country_breakdown",
            FinancialObservation.value_status == "reported",
        )
    ):
        if currency != "USD":
            non_usd.add(project_id)
        elif amount is not None:
            usd_lines[project_id] = usd_lines.get(project_id, Decimal(0)) + amount
    totals = dict(
        session.execute(
            select(FinancialObservation.project_id, FinancialObservation.amount).where(
                FinancialObservation.source_id == API_SOURCE,
                FinancialObservation.observation_key.like("%:total_gcf"),
            )
        ).all()
    )
    usd_only = [p for p in totals if p not in non_usd]
    usd_only_equal = sum(1 for p in usd_only if usd_lines.get(p) == totals[p])
    return {
        "project_rows_by_source": {str(k): int(v) for k, v in projects.items()},
        "observations_by_source_and_flow": observations,
        "documents": _count(session, select(Document.id)),
        "document_families": int(
            session.scalar(select(func.count(func.distinct(Document.family_id)))) or 0
        ),
        "country_aggregate_rows": _count(session, select(CountryAggregate.id)),
        "country_aggregate_countries": int(
            session.scalar(select(func.count(func.distinct(CountryAggregate.iso3)))) or 0
        ),
        "historical_staging_rows": _count(session, select(HistoricalStagingRecord.id)),
        "checks": {
            "duplicate_observation_keys": duplicate_keys,
            "duplicate_enrichments_per_project": enrichment_duplicates,
            "api_observations_attached_to_non_gcf_projects": api_on_non_gcf,
            "api_project_totals_with_a_currency": api_totals_with_currency,
            "country_aggregates_in_financial_observations": 0,  # separate table by design
            "documents_counted_as_projects": _count(
                session, select(Project.id).where(Project.source_id == "climate_project_explorer")
            ),
            "readiness_rows_counted_as_gcf_funded_projects": _count(
                session,
                select(Project.id).where(
                    Project.source_id == "gcf_projects",
                    Project.record_level != "gcf_funded_project",
                ),
            ),
        },
        "gcf_api_internal_consistency": {
            "projects_with_only_usd_gcf_funding_lines": len(usd_only),
            "of_which_line_sum_equals_published_total": usd_only_equal,
            "projects_with_non_usd_gcf_lines_not_comparable": len(non_usd),
        },
        "relationships": relationship_counts(session),
    }


def relationship_counts(session: Session) -> dict[str, Any]:
    rel = {
        f"{t}|{s}|{v}": int(n)
        for t, s, v, n in session.execute(
            select(
                ProjectRelationship.relation_type,
                ProjectRelationship.status,
                ProjectRelationship.verification_state,
                func.count(),
            ).group_by(
                ProjectRelationship.relation_type,
                ProjectRelationship.status,
                ProjectRelationship.verification_state,
            )
        ).all()
    }
    docs = {
        f"{t}|{v}": int(n)
        for t, v, n in session.execute(
            select(
                DocumentLink.relation_type, DocumentLink.verification_state, func.count()
            ).group_by(DocumentLink.relation_type, DocumentLink.verification_state)
        ).all()
    }
    groups = {
        f"{t}|{v}": (int(n), int(m or 0))
        for t, v, n, m in session.execute(
            select(
                RecordGroup.member_relation_type,
                RecordGroup.verification_state,
                func.count(),
                func.sum(RecordGroup.member_count),
            ).group_by(RecordGroup.member_relation_type, RecordGroup.verification_state)
        ).all()
    }
    enrich = {
        f"{t}|{v}": int(n)
        for t, v, n in session.execute(
            select(
                ProjectEnrichment.relation_type, ProjectEnrichment.verification_state, func.count()
            ).group_by(ProjectEnrichment.relation_type, ProjectEnrichment.verification_state)
        ).all()
    }
    return {
        "project_relationships": rel,
        "document_links": docs,
        "record_groups_(groups,members)": groups,
        "enrichments": enrich,
    }


def historical_comparison_report(session: Session) -> dict[str, Any]:
    """RESTRICTED internal comparison: historical Tot_Fin (USD thousands) vs API TotalValue
    (currency not stated). Reported side by side; never summed or substituted."""
    rows = session.scalars(select(HistoricalStagingRecord)).all()
    api_totals = dict(
        session.execute(
            select(FinancialObservation.project_id, FinancialObservation.amount).where(
                FinancialObservation.source_id == API_SOURCE,
                FinancialObservation.observation_key.like("%:total_value"),
            )
        ).all()
    )
    equal = differ = not_comparable = 0
    for row in rows:
        api = api_totals.get(row.matched_project_id or "")
        if row.total_financing is None or api is None:
            not_comparable += 1
        elif row.total_financing * 1000 == api:
            equal += 1
        else:
            differ += 1
    return {
        "access": "RESTRICTED internal comparison (gcf_historical provenance unverified)",
        "historical_rows": len(rows),
        "matched_to_current_export": sum(1 for r in rows if r.matched_project_id),
        "unparseable_totals": sum(1 for r in rows if r.value_status != "reported"),
        "tot_fin_x1000_equals_api_total_value": equal,
        "tot_fin_x1000_differs_from_api_total_value": differ,
        "not_comparable": not_comparable,
        "note": "Historical values are a 2020 snapshot in USD thousands; API TotalValue states no "
        "currency. Differences are expected (restructuring, later approvals) and are not errors.",
    }


REPORTS: dict[str, Callable[[Session], dict[str, Any]]] = {
    "gcf-enrichment": gcf_enrichment_report,
    "reconciliation": reconciliation_report,
    "historical-comparison": historical_comparison_report,
}
