"""Idempotent writer: records -> database, with per-run accounting.

Per project (identity = ``<source_id>:<source_project_id>``):

* not in the database          -> inserted
* present, same content hash   -> unchanged (nothing written)
* present, different content   -> updated (the row and its children are replaced)
* invalid (no ID / no title / repeated ID in one batch) -> rejected (reason recorded)
* in the database but no longer in the source file -> removed (reported, never silent)

Re-running an import on the same file therefore writes nothing and never duplicates rows.
"""

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from compassio_api.db.models import (
    ClimateAnnotation,
    DataQualityWarning,
    FinancialObservation,
    ImportRun,
    Project,
    ProjectCountry,
    ProjectRelationship,
)
from compassio_api.ingest.records import ProjectRec, validated

BATCH = 2000


@dataclass
class IngestResult:
    source_key: str
    source_id: str
    run_id: int
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0
    removed: int = 0
    observations_written: int = 0
    rejection_reasons: Counter[str] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rejection_reasons"] = dict(self.rejection_reasons)
        return data


def start_run(session: Session, source_key: str, input_sha256: dict[str, str]) -> ImportRun:
    run = ImportRun(
        source_key=source_key,
        input_sha256=input_sha256,
        started_at=datetime.now(UTC),
        status="running",
        inserted=0,
        updated=0,
        unchanged=0,
        rejected=0,
        removed=0,
    )
    session.add(run)
    session.flush()
    return run


def _reject_reason(rec: ProjectRec) -> str | None:
    if not rec.source_project_id.strip():
        return "missing_source_project_id"
    if not rec.title.strip():
        return "missing_title"
    if len(rec.id) > 240:
        return "identifier_too_long"
    return None


def write_records(
    session: Session, run: ImportRun, source_id: str, records: Iterable[ProjectRec]
) -> IngestResult:
    """Write one source's records. The caller owns the transaction (commit/rollback)."""
    result = IngestResult(source_key=run.source_key, source_id=source_id, run_id=run.id)
    existing: dict[str, str] = dict(
        session.execute(
            select(Project.id, Project.content_sha256).where(Project.source_id == source_id)
        ).all()
    )
    seen: set[str] = set()
    to_write: list[tuple[ProjectRec, str]] = []
    to_replace: list[str] = []
    for rec in records:
        if rec.source_id != source_id:
            raise ValueError(f"record {rec.id} does not belong to source {source_id}")
        reason = _reject_reason(rec)
        if reason is None and rec.id in seen:
            reason = "duplicate_identifier_in_source"
        if reason is not None:
            result.rejected += 1
            result.rejection_reasons[reason] += 1
            continue
        seen.add(rec.id)
        digest = rec.content_sha256()
        previous = existing.get(rec.id)
        if previous == digest:
            result.unchanged += 1
            continue
        if previous is None:
            result.inserted += 1
        else:
            result.updated += 1
            to_replace.append(rec.id)
        to_write.append((rec, digest))

    stale = sorted(set(existing) - seen)
    result.removed = len(stale)
    for ids in _chunks(to_replace + stale):
        session.execute(delete(Project).where(Project.id.in_(ids)))
    for batch in _chunks(to_write):
        result.observations_written += _insert_chunk(session, run.id, batch)

    run.inserted, run.updated, run.unchanged = result.inserted, result.updated, result.unchanged
    run.rejected, run.removed = result.rejected, result.removed
    if result.rejection_reasons:
        run.message = json.dumps({"rejections": dict(result.rejection_reasons)})
    return result


def _chunks[T](items: Sequence[T]) -> Iterable[Sequence[T]]:
    for start in range(0, len(items), BATCH):
        yield items[start : start + BATCH]


def _insert_chunk(session: Session, run_id: int, chunk: Sequence[tuple[ProjectRec, str]]) -> int:
    projects: list[dict[str, Any]] = []
    countries: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for rec, digest in chunk:
        projects.append(
            {
                "id": rec.id,
                "source_id": rec.source_id,
                "source_project_id": rec.source_project_id,
                "record_level": rec.record_level,
                "title": rec.title,
                "description": rec.description,
                "recipient_label": rec.recipient_label,
                "region": rec.region,
                "multi_country": rec.multi_country,
                "sector_name": rec.sector_name,
                "sector_code": rec.sector_code,
                "sector_vocabulary": rec.sector_vocabulary,
                "year": rec.year,
                "year_type": rec.year_type,
                "date_value": rec.date_value,
                "date_precision": rec.date_precision,
                "date_estimated": rec.date_estimated,
                "status": rec.status,
                "group_key": rec.group_key,
                "group_meaning": rec.group_meaning,
                "source_reference": rec.source_reference,
                "attributes": rec.attributes,
                "content_sha256": digest,
                "import_run_id": run_id,
            }
        )
        for position, country in enumerate(rec.countries):
            countries.append(
                {
                    "project_id": rec.id,
                    "position": position,
                    "country_name": country.name,
                    "iso3": country.iso3,
                    "mapping_method": country.method,
                }
            )
        for ann in rec.annotations:
            annotations.append(
                {
                    "project_id": rec.id,
                    "annotation_source_id": ann.annotation_source_id,
                    "scheme": ann.scheme,
                    "kind": ann.kind,
                    "is_model_prediction": False,
                    "overall": ann.overall,
                    "mitigation": ann.mitigation,
                    "adaptation": ann.adaptation,
                    "is_climate_related": ann.is_climate_related,
                    "label": ann.label,
                    "raw_value": ann.raw_value,
                    "provenance": ann.provenance,
                }
            )
        for obs in rec.observations:
            checked = validated(obs)
            if checked.value_status == "invalid" and obs.value_status == "reported":
                rec.warn(
                    "amount_rejected_by_finance_contract",
                    "A published amount violates the financial data contract (e.g. a negative "
                    "commitment) and is shown as invalid, not used in any total.",
                    "amount",
                )
            observations.append(
                {
                    "project_id": rec.id,
                    "source_id": rec.source_id,
                    "observation_key": checked.key,
                    "flow_kind": checked.flow_kind,
                    "level": checked.level,
                    "financing_type": checked.financing_type,
                    "is_component": checked.is_component,
                    "amount": checked.amount,
                    "raw_value": checked.raw_value,
                    "value_status": checked.value_status,
                    "unit": checked.unit,
                    "currency": checked.currency,
                    "unit_status": checked.unit_status,
                    "price_basis": checked.price_basis,
                    "effective_date": checked.effective_date,
                    "effective_year": checked.effective_year,
                    "date_meaning": checked.date_meaning,
                    "multi_country": checked.multi_country,
                    "estimated": checked.estimated,
                    "recommended_for_aggregates": checked.recommended_for_aggregates,
                    "source_reference": checked.source_reference,
                    "country_iso3": checked.country_iso3,
                }
            )
        for warning in rec.warnings:
            warnings.append(
                {
                    "project_id": rec.id,
                    "code": warning.code,
                    "field": warning.field,
                    "message": warning.message,
                }
            )
    session.execute(insert(Project), projects)
    for model, rows in (
        (ProjectCountry, countries),
        (ClimateAnnotation, annotations),
        (FinancialObservation, observations),
        (DataQualityWarning, warnings),
    ):
        if rows:
            session.execute(insert(model), rows)
    return len(observations)


def finish_run(run: ImportRun, status: str, message: str | None = None) -> None:
    run.status = status
    run.finished_at = datetime.now(UTC)
    if message:
        run.message = message


# ------------------------------------------------------------------ cross-source relationships
def rebuild_reference_code_links(session: Session) -> dict[str, int]:
    """CFU rows whose project name embeds a GCF code (e.g. "(FP001)") -> that GCF project.

    Status ``probable_match_reference_code`` (docs/data/cross_source_overlap.md §4): a link for
    review and display, never a merge, and amounts are never added across the two sources.
    """
    session.execute(
        delete(ProjectRelationship).where(
            ProjectRelationship.relation_type == "cross_source_reference_code"
        )
    )
    gcf_ids = set(
        session.scalars(select(Project.id).where(Project.source_id == "gcf_projects")).all()
    )
    rows = session.execute(
        select(Project.id, Project.title, Project.attributes).where(
            Project.source_id == "climate_funds_update"
        )
    ).all()
    links: list[dict[str, Any]] = []
    unresolved = 0
    for project_id, title, attributes in rows:
        code = attributes.get("gcf_reference_code")
        if not code:
            continue
        target = f"gcf_projects:{code}"
        if target not in gcf_ids:
            unresolved += 1
            continue
        links.append(
            {
                "from_project_id": project_id,
                "to_project_id": target,
                "relation_type": "cross_source_reference_code",
                "status": "probable_match_reference_code",
                "method": "GCF reference code embedded in the CFU project name",
                "evidence": f"CFU name: {title[:300]}",
                "human_reviewed": False,
                "asserted_by_source_id": "climate_funds_update",
                "verification_state": "deterministic_identifier_match",
                "last_verified_on": date.today(),
            }
        )
    if links:
        session.execute(insert(ProjectRelationship), links)
    return {"cfu_to_gcf_links": len(links), "cfu_codes_without_gcf_project": unresolved}
