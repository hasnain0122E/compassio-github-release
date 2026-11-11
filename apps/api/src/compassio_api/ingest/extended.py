"""Idempotent writers for enrichment, documents, country aggregates, historical staging and
record groups. Same accounting as projects: inserted / updated / unchanged / removed."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, delete, func, insert, inspect, select
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
    RecordGroup,
)
from compassio_api.ingest import gcf_api
from compassio_api.ingest.records import ObservationRec

EXCLUDED_FROM_COMPARISON = frozenset({"id", "import_run_id", "last_verified_on"})


@dataclass
class SyncResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _normal(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        moment = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
        return moment.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def sync_rows(
    session: Session,
    model: type[Any],
    scope: Sequence[ColumnElement[bool]],
    key_fields: tuple[str, ...],
    rows: list[dict[str, Any]],
    run_id: int | None = None,
) -> SyncResult:
    """Make the scoped rows equal to ``rows`` with minimal writes (never duplicates)."""
    mapper = inspect(model)
    pk = mapper.primary_key[0]
    columns = [c.key for c in mapper.columns]
    compared = [c for c in columns if c not in EXCLUDED_FROM_COMPARISON]
    existing: dict[tuple[object, ...], tuple[object, dict[str, object]]] = {}
    for obj in session.scalars(select(model).where(*scope)):
        key = tuple(getattr(obj, f) for f in key_fields)
        existing[key] = (
            getattr(obj, pk.key),
            {c: _normal(getattr(obj, c)) for c in compared},
        )
    result = SyncResult()
    to_insert: list[dict[str, Any]] = []
    to_delete: list[object] = []
    seen: set[tuple[object, ...]] = set()
    for row in rows:
        key = tuple(row[f] for f in key_fields)
        if key in seen:
            raise ValueError(f"duplicate key {key} in {model.__tablename__} input")
        seen.add(key)
        values = {c: _normal(row.get(c)) for c in compared if c in row}
        if key in existing:
            pk_value, current = existing[key]
            if all(current.get(c) == v for c, v in values.items()):
                result.unchanged += 1
                continue
            to_delete.append(pk_value)
            result.updated += 1
        else:
            result.inserted += 1
        full = dict(row)
        if run_id is not None and "import_run_id" in columns:
            full["import_run_id"] = run_id
        to_insert.append(full)
    stale = [existing[k][0] for k in existing if k not in seen]
    result.removed = len(stale)
    for start in range(0, len(to_delete + stale), 2000):
        chunk = (to_delete + stale)[start : start + 2000]
        session.execute(delete(model).where(pk.in_(chunk)))
    for start in range(0, len(to_insert), 2000):
        session.execute(insert(model), to_insert[start : start + 2000])
    return result


def _digest(payload: object) -> str:
    text = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- aggregates etc.
def write_country_aggregates(
    session: Session, run: ImportRun, source_id: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    result = sync_rows(
        session,
        CountryAggregate,
        [CountryAggregate.source_id == source_id],
        ("source_id", "iso3", "measure"),
        rows,
        run.id,
    )
    return {"country_aggregates": result.as_dict(), "rows": len(rows)}


def write_documents(
    session: Session, run: ImportRun, source_id: str, documents: list[dict[str, Any]]
) -> dict[str, Any]:
    for doc in documents:
        doc["content_sha256"] = _digest({k: v for k, v in doc.items() if k != "content_sha256"})
    docs = sync_rows(
        session, Document, [Document.source_id == source_id], ("id",), documents, run.id
    )
    return {
        "documents": docs.as_dict(),
        "rows": len(documents),
        "families": len({d["family_id"] for d in documents}),
    }


def rebuild_document_links(session: Session) -> dict[str, int]:
    """Document -> GCF project links from codes in each document's own metadata (idempotent)."""
    session.execute(delete(DocumentLink))
    gcf_ids = set(
        session.scalars(select(Project.id).where(Project.source_id == "gcf_projects")).all()
    )
    rows: list[dict[str, Any]] = []
    unresolved = 0
    today = datetime.now(UTC).date()
    for doc_id, source_id, attributes in session.execute(
        select(Document.id, Document.source_id, Document.attributes)
    ):
        codes = list(attributes.get("gcf_codes_in_metadata") or [])
        for code in codes:
            target = f"gcf_projects:{code}"
            if target not in gcf_ids:
                unresolved += 1
                continue
            single = len(codes) == 1
            rows.append(
                {
                    "document_id": doc_id,
                    "project_id": target,
                    "relation_type": "document_of_project",
                    "match_method": "GCF reference code in the document's own catalogue metadata",
                    "match_evidence": f"GCF code {code} in CPE family name/document title/summary"
                    + ("" if single else f" (document cites {len(codes)} codes)"),
                    "asserted_by_source_id": source_id,
                    "verification_state": "deterministic_identifier_match"
                    if single
                    else "candidate_requires_review",
                    "review_status": "not_reviewed",
                    "last_verified_on": today,
                }
            )
    if rows:
        session.execute(insert(DocumentLink), rows)
    return {
        "links": len(rows),
        "single_code_links": sum(1 for r in rows if r["verification_state"].startswith("determ")),
        "multi_code_candidates": sum(1 for r in rows if r["verification_state"].startswith("cand")),
        "codes_without_gcf_project": unresolved,
    }


def write_historical(
    session: Session, run: ImportRun, source_id: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    gcf_ids = set(
        session.scalars(select(Project.id).where(Project.source_id == "gcf_projects")).all()
    )
    for row in rows:
        target = f"gcf_projects:{row['source_record_id']}"
        row["matched_project_id"] = target if target in gcf_ids else None
    result = sync_rows(
        session,
        HistoricalStagingRecord,
        [HistoricalStagingRecord.source_id == source_id],
        ("source_id", "source_record_id"),
        rows,
        run.id,
    )
    return {
        "historical_staging": result.as_dict(),
        "rows": len(rows),
        "matched_to_current_export": sum(1 for r in rows if r["matched_project_id"]),
    }


# ------------------------------------------------------------------------------ GCF API
def _export_views(session: Session) -> dict[str, gcf_api.ExportView]:
    projects = session.scalars(select(Project).where(Project.source_id == "gcf_projects")).all()
    iso: dict[str, set[str]] = {}
    for project_id, code in session.execute(
        select(ProjectCountry.project_id, ProjectCountry.iso3)
        .join(Project, Project.id == ProjectCountry.project_id)
        .where(Project.source_id == "gcf_projects", ProjectCountry.iso3.is_not(None))
    ):
        iso.setdefault(project_id, set()).add(str(code))
    amounts = dict(
        session.execute(
            select(FinancialObservation.project_id, FinancialObservation.amount).where(
                FinancialObservation.source_id == "gcf_projects",
                FinancialObservation.flow_kind == "gcf_financing",
            )
        ).all()
    )
    views: dict[str, gcf_api.ExportView] = {}
    for p in projects:
        attrs = p.attributes
        views[p.source_project_id] = gcf_api.ExportView(
            title=p.title,
            board_meeting=attrs.get("board_meeting"),
            theme=attrs.get("theme"),
            sector_type=attrs.get("gcf_sector_type"),
            entity=attrs.get("accredited_entity"),
            iso3=frozenset(iso.get(p.id, set())),
            fa_financing=amounts.get(p.id),
        )
    return views


def _observation_row(project_id: str, source_id: str, obs: ObservationRec) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "source_id": source_id,
        "observation_key": obs.key,
        "flow_kind": obs.flow_kind,
        "level": obs.level,
        "financing_type": obs.financing_type,
        "is_component": obs.is_component,
        "amount": obs.amount,
        "raw_value": obs.raw_value,
        "value_status": obs.value_status,
        "unit": obs.unit,
        "currency": obs.currency,
        "unit_status": obs.unit_status,
        "price_basis": obs.price_basis,
        "effective_date": obs.effective_date,
        "effective_year": obs.effective_year,
        "date_meaning": obs.date_meaning,
        "multi_country": obs.multi_country,
        "estimated": obs.estimated,
        "recommended_for_aggregates": obs.recommended_for_aggregates,
        "source_reference": obs.source_reference,
        "country_iso3": obs.country_iso3,
    }


def write_gcf_api_enrichment(
    session: Session,
    run: ImportRun,
    records: list[dict[str, Any]],
    snapshot_id: str,
    retrieved_at: datetime,
) -> dict[str, Any]:
    source_id = gcf_api.SOURCE_ID
    views = _export_views(session)
    enrichments: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    unmatched: list[str] = []
    seen_refs: set[str] = set()
    for record in records:
        ref = str(record.get("ApprovedRef") or "")
        if not ref or ref in seen_refs:
            raise ValueError(f"GCF API snapshot has a blank or repeated ApprovedRef: {ref!r}")
        seen_refs.add(ref)
        view = views.get(ref)
        if view is None:
            unmatched.append(ref)
            continue
        project_id = f"gcf_projects:{ref}"
        rec = gcf_api.build_enrichment(record, project_id, view, retrieved_at)
        enrichments.append(
            {
                "project_id": project_id,
                "source_id": source_id,
                "snapshot_id": snapshot_id,
                "source_record_id": ref,
                "relation_type": gcf_api.RELATION,
                "match_method": gcf_api.MATCH_METHOD,
                "match_evidence": f"ApprovedRef {ref} == Ref # {ref}",
                "verification_state": "deterministic_identifier_match",
                "review_status": "not_reviewed",
                "last_verified_on": retrieved_at.date(),
                "official_url": rec.official_url,
                "approval_date": rec.approval_date,
                "approval_date_type": "GCF Board approval date (API 'ApprovalDate')"
                if rec.approval_date
                else None,
                "approval_status": "approved by the GCF Board (ApprovalDate published)"
                if rec.approval_date
                else None,
                "project_status": rec.project_status,
                "status_as_of": retrieved_at if rec.project_status else None,
                "status_as_of_meaning": (
                    "The API publishes no as-of date for 'Status'; this is the snapshot "
                    "retrieval time."
                )
                if rec.project_status
                else None,
                "values": rec.values,
                "conflicts": rec.conflicts,
                "content_sha256": rec.content_sha256(),
            }
        )
        observations.extend(_observation_row(project_id, source_id, o) for o in rec.observations)
    enrichment_result = sync_rows(
        session,
        ProjectEnrichment,
        [ProjectEnrichment.source_id == source_id],
        ("project_id",),
        enrichments,
    )
    observation_result = sync_rows(
        session,
        FinancialObservation,
        [FinancialObservation.source_id == source_id],
        ("source_id", "observation_key"),
        observations,
    )
    export_refs = set(views)
    return {
        "api_records": len(records),
        "matched_export_projects": len(enrichments),
        "api_records_not_in_export": sorted(unmatched),
        "export_projects_not_in_api": sorted(export_refs - seen_refs),
        "enrichments": enrichment_result.as_dict(),
        "observations": observation_result.as_dict(),
        "observation_rows": len(observations),
    }


# ----------------------------------------------------------------------------- record groups
GROUP_TYPES = {
    "adb_pakistan": (
        "adb_project_number",
        "instrument_of_adb_project",
        "ADB project number embedded in the IATI identifier (XM-DAC-46004-<number>-<instrument>)",
        "deterministic_identifier_structure",
    ),
    "aiddata": (
        "aiddata_parent_package",
        "member_of_aiddata_parent_package",
        "AidData 'Parent ID' field (related records, not the same record)",
        "deterministic_identifier_match",
    ),
}


def rebuild_record_groups(session: Session) -> dict[str, int]:
    session.execute(delete(RecordGroup))
    rows = session.execute(
        select(Project.group_key, Project.source_id, func.count())
        .where(Project.group_key.is_not(None))
        .group_by(Project.group_key, Project.source_id)
    ).all()
    today = datetime.now(UTC).date()
    inserts: list[dict[str, Any]] = []
    for key, source_id, count in rows:
        spec = GROUP_TYPES.get(source_id)
        if spec is None:
            continue
        inserts.append(
            {
                "group_key": key,
                "source_id": source_id,
                "group_type": spec[0],
                "member_relation_type": spec[1],
                "match_method": spec[2],
                "verification_state": spec[3],
                "review_status": "not_reviewed",
                "last_verified_on": today,
                "member_count": int(count),
            }
        )
    if inserts:
        session.execute(insert(RecordGroup), inserts)
    summary: dict[str, int] = {}
    for row in inserts:
        summary[row["group_type"]] = summary.get(row["group_type"], 0) + 1
    return summary
