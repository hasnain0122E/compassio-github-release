"""Orchestrates one ingestion: verify inputs -> sync source metadata -> build -> write -> link.

Inputs are refused unless:

* every canonical raw file matches the committed source manifest (re-hashed now; the manifest
  itself is only READ -- it belongs to the ML track and is never modified here);
* the research table matches the committed Task 003 lock;
* backend-staging snapshots pass the backend registry validation (hash, size, no stray files).
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from compassio_api.db.models import ImportRun, Source
from compassio_api.ingest import adb, cfu, extended, gcf, remaining, research
from compassio_api.ingest.loader import (
    finish_run,
    rebuild_reference_code_links,
    start_run,
    write_records,
)
from compassio_api.staging.registry import (
    BACKEND_SOURCES,
    BackendRegistry,
    load_registry,
    raw_db_dir,
    save_registry,
    validate_registry,
)
from compassio_ml.audit.loaders import SourceData, single_file
from compassio_ml.data.layout import DataLayout, MissingSourceDataError
from compassio_ml.data.manifest import SourceManifest
from compassio_ml.data.manifest_io import manifest_path, validate_manifest
from compassio_ml.data.sources import SOURCES_BY_ID
from compassio_ml.integrity.hashing import sha256_file

LOCK_RELPATH = Path("configs") / "research_split_v1.lock.json"
# Sources whose provenance could not be verified: staged for internal comparison only.
RESTRICTED_SOURCES = {
    "gcf_historical": "Origin unconfirmed (Mendeley id returned 404; source_rights_matrix.md); "
    "restricted internal comparison/staging only, never served by the API.",
}


class IngestInputError(RuntimeError):
    """A required input is missing or does not match its registered checksum."""


Writer = Callable[[Session, ImportRun], dict[str, Any]]


@dataclass(frozen=True)
class Plan:
    input_sha256: dict[str, str]
    write: Writer


@dataclass(frozen=True)
class Context:
    layout: DataLayout
    manifest: SourceManifest
    registry: BackendRegistry
    repo_root: Path

    @property
    def data(self) -> SourceData:
        return SourceData(self.layout)


def load_manifest(layout: DataLayout) -> SourceManifest:
    report = validate_manifest(layout)
    if not report.ok:
        raise IngestInputError(
            "source manifest validation failed:\n  " + "\n  ".join(report.errors)
        )
    return SourceManifest.model_validate_json(manifest_path(layout).read_text(encoding="utf-8"))


def sync_sources(session: Session, manifest: SourceManifest, registry: BackendRegistry) -> int:
    """Copy source metadata (canonical manifest + latest backend snapshots) into ``sources``.

    Rights statuses are copied, never changed; backend sources are always ``not_reviewed``.
    """
    now = datetime.now(UTC)
    for entry in manifest.entries:
        definition = SOURCES_BY_ID[entry.source_id]
        version = (
            f"published {entry.source_publication_date}"
            if entry.source_publication_date
            else "publication date not recorded; the file SHA-256 identifies the version"
        )
        session.merge(
            Source(
                source_id=entry.source_id,
                name=definition.title,
                publisher=entry.publisher,
                version_info=version,
                file_relpath=entry.file_relpath,
                file_sha256=entry.sha256,
                reference_url=str(entry.publisher_reference_url)
                if entry.publisher_reference_url
                else definition.reference_url,
                rights_status=str(entry.rights_status),
                rights_evidence=entry.rights_evidence,
                license_notes=entry.published_license_notes,
                observation_type=entry.unit_of_observation,
                audited_record_count=entry.record_count_after_inspection,
                synced_at=now,
                source_registry="canonical",
                access_tier="restricted_internal"
                if entry.source_id in RESTRICTED_SOURCES
                else "standard",
            )
        )
    count = len(manifest.entries)
    for backend_id in BACKEND_SOURCES:
        snap = registry.latest(backend_id)
        if snap is None:
            continue
        session.merge(
            Source(
                source_id=backend_id,
                name=snap.description,
                publisher=snap.publisher,
                version_info=f"snapshot {snap.snapshot_id}, retrieved "
                f"{snap.retrieved_at.isoformat()}"
                + (
                    f"; publisher update date {snap.source_update_date}"
                    if snap.source_update_date
                    else ""
                ),
                file_relpath=f"raw_db/{snap.stored_relpath}",
                file_sha256=snap.sha256,
                reference_url=snap.landing_url,
                rights_status=snap.rights_status,
                rights_evidence=None,
                license_notes=snap.attribution_notes,
                observation_type=snap.unit_of_observation,
                audited_record_count=None,
                synced_at=now,
                source_registry="backend_staging",
                access_tier="standard",
            )
        )
        count += 1
    return count


def _raw_hashes(manifest: SourceManifest, *source_ids: str) -> dict[str, str]:
    by_id = {e.source_id: e.sha256 for e in manifest.entries}
    missing = [s for s in source_ids if s not in by_id]
    if missing:
        raise IngestInputError(f"sources not registered in the manifest: {missing}")
    return {f"raw:{s}": by_id[s] for s in source_ids}


def _project_plan(source_id: str, records: list[Any], hashes: dict[str, str]) -> Plan:
    def write(session: Session, run: ImportRun) -> dict[str, Any]:
        return write_records(session, run, source_id, records).as_dict()

    return Plan(hashes, write)


def research_plan(ctx: Context) -> Plan:
    import pandas as pd

    table_path = ctx.layout.processed / "research_projects.parquet"
    text_path = ctx.layout.processed / "research_text_originals.parquet"
    lock_path = ctx.repo_root / LOCK_RELPATH
    for path in (table_path, text_path, lock_path):
        if not path.is_file():
            raise IngestInputError(
                f"missing {path}; run `uv run compassio-research build` (Task 003) first"
            )
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    table_sha = sha256_file(table_path)
    if table_sha != lock["table"]["sha256"]:
        raise IngestInputError(
            f"research table sha256 {table_sha} != committed lock {lock['table']['sha256']}"
        )
    records = research.build_research_records(
        pd.read_parquet(table_path), pd.read_parquet(text_path)
    )
    hashes = _raw_hashes(ctx.manifest, "research_paper", "aiddata")
    hashes["processed:research_projects"] = table_sha
    hashes["processed:research_text_originals"] = sha256_file(text_path)
    return _project_plan(research.SOURCE_ID, records, hashes)


def gcf_plan(ctx: Context) -> Plan:
    data = ctx.data
    records = gcf.build_gcf_records(data.gcf_projects, gcf.gcf_country_map(data.gcf_countries))
    return _project_plan(
        gcf.SOURCE_ID, records, _raw_hashes(ctx.manifest, "gcf_projects", "gcf_countries")
    )


def country_lookup(
    gcf_map: dict[str, tuple[str, str | None]], aiddata_map: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """Exact-name lookup from two registered sources; a name the two disagree on is dropped."""
    lookup = {name: (iso3, "gcf_countries_exact_name") for name, (iso3, _) in gcf_map.items()}
    for name, iso3 in aiddata_map.items():
        if name in lookup:
            if lookup[name][0] != iso3:
                del lookup[name]
            continue
        lookup[name] = (iso3, "aiddata_recipient_exact_name")
    return lookup


def cfu_plan(ctx: Context) -> Plan:
    import pandas as pd

    data = ctx.data
    table_path = ctx.layout.processed / "research_projects.parquet"
    if not table_path.is_file():
        raise IngestInputError(f"missing {table_path}; needed for the AidData country names")
    names = pd.read_parquet(table_path, columns=["recipient", "recipient_iso3"])
    lookup = country_lookup(
        gcf.gcf_country_map(data.gcf_countries), research.aiddata_country_lookup(names)
    )
    records = cfu.build_cfu_records(data.cfu["Projects"], lookup)
    hashes = _raw_hashes(ctx.manifest, "climate_funds_update", "gcf_countries", "aiddata")
    hashes["processed:research_projects"] = sha256_file(table_path)
    return _project_plan(cfu.SOURCE_ID, records, hashes)


def adb_plan(ctx: Context) -> Plan:
    frames = ctx.data.adb
    records = adb.build_adb_records(
        frames.activities, frames.transactions, frames.sectors, frames.generated_datetime
    )
    return _project_plan(adb.SOURCE_ID, records, _raw_hashes(ctx.manifest, "adb_pakistan"))


def readiness_plan(ctx: Context) -> Plan:
    data = ctx.data
    records = remaining.build_readiness_records(
        data.gcf_readiness, gcf.gcf_country_map(data.gcf_countries)
    )
    return _project_plan(
        remaining.READINESS_SOURCE,
        records,
        _raw_hashes(ctx.manifest, "gcf_readiness", "gcf_countries"),
    )


def countries_plan(ctx: Context) -> Plan:
    path = single_file(ctx.layout.raw / "gcf_countries", ".xlsx", "gcf_countries")
    rows = remaining.build_country_aggregates(
        ctx.data.gcf_countries, remaining.export_snapshot_date(path)
    )

    def write(session: Session, run: ImportRun) -> dict[str, Any]:
        return extended.write_country_aggregates(session, run, remaining.COUNTRIES_SOURCE, rows)

    return Plan(_raw_hashes(ctx.manifest, "gcf_countries"), write)


def cpe_plan(ctx: Context) -> Plan:
    documents = remaining.build_documents(ctx.data.cpe)

    def write(session: Session, run: ImportRun) -> dict[str, Any]:
        return extended.write_documents(session, run, remaining.CPE_SOURCE, documents)

    return Plan(_raw_hashes(ctx.manifest, "climate_project_explorer"), write)


def historical_plan(ctx: Context) -> Plan:
    rows = remaining.build_historical(ctx.data.gcf_historical)

    def write(session: Session, run: ImportRun) -> dict[str, Any]:
        return extended.write_historical(session, run, remaining.HISTORICAL_SOURCE, rows)

    return Plan(_raw_hashes(ctx.manifest, "gcf_historical"), write)


def gcf_api_plan(ctx: Context) -> Plan:
    report = validate_registry(ctx.layout.root)
    if not report.ok:
        raise IngestInputError("backend registry invalid:\n  " + "\n  ".join(report.errors))
    snap = ctx.registry.latest("gcf_api_projects")
    if snap is None:
        raise IngestInputError(
            "no gcf_api_projects snapshot; run `uv run compassio-db fetch --source "
            "gcf_api_projects` first"
        )
    payload = json.loads(
        (raw_db_dir(ctx.layout.root) / snap.stored_relpath).read_text(encoding="utf-8")
    )
    if not isinstance(payload, list):
        raise IngestInputError("gcf_api_projects snapshot is not a JSON list")

    def write(session: Session, run: ImportRun) -> dict[str, Any]:
        result = extended.write_gcf_api_enrichment(
            session, run, payload, snap.snapshot_id, snap.retrieved_at
        )
        result["snapshot_id"] = snap.snapshot_id
        return result

    return Plan({f"raw_db:gcf_api_projects:{snap.snapshot_id}": snap.sha256}, write)


INGESTERS: dict[str, Callable[[Context], Plan]] = {
    "research_paper": research_plan,
    "gcf_projects": gcf_plan,
    "climate_funds_update": cfu_plan,
    "adb_pakistan": adb_plan,
    "gcf_readiness": readiness_plan,
    "gcf_countries": countries_plan,
    "climate_project_explorer": cpe_plan,
    "gcf_historical": historical_plan,
    "gcf_api_projects": gcf_api_plan,
}
# Task 006 core project sources.
ORDER = ("research_paper", "gcf_projects", "climate_funds_update", "adb_pakistan")
# Everything, in dependency order: GCF projects before CFU/CPE/historical/API (link targets).
ALL_ORDER = (
    *ORDER,
    "gcf_readiness",
    "gcf_countries",
    "climate_project_explorer",
    "gcf_historical",
    "gcf_api_projects",
)


def ingest(
    engine: Engine, layout: DataLayout, source_keys: list[str], repo_root: Path
) -> dict[str, Any]:
    manifest = load_manifest(layout)
    registry = load_registry(layout.root)
    ctx = Context(layout, manifest, registry, repo_root)
    report: dict[str, Any] = {"sources": {}, "links": {}}
    with Session(engine) as session, session.begin():
        report["sources_synced"] = sync_sources(session, manifest, registry)
    for key in source_keys:
        try:
            plan = INGESTERS[key](ctx)
        except MissingSourceDataError as exc:
            raise IngestInputError(str(exc)) from exc
        with Session(engine) as session:
            run = start_run(session, key, plan.input_sha256)
            session.commit()
            try:
                result = plan.write(session, run)
                finish_run(run, "completed", json.dumps(result, default=str, sort_keys=True))
                session.commit()
            except Exception as exc:
                session.rollback()
                failed = session.get(ImportRun, run.id)
                if failed is not None:
                    finish_run(failed, "failed", f"{type(exc).__name__}: {exc}")
                    session.commit()
                raise
        report["sources"][key] = result
        if key == "gcf_api_projects":
            _mark_ingested(layout.root, registry)
    with Session(engine) as session, session.begin():
        report["links"] = rebuild_reference_code_links(session)
        report["links"]["document_links"] = extended.rebuild_document_links(session)
        report["links"]["record_groups"] = extended.rebuild_record_groups(session)
    return report


def _mark_ingested(data_root: Path, registry: BackendRegistry) -> None:
    snap = registry.latest("gcf_api_projects")
    if snap is None or snap.ingestion_status == "ingested":
        return
    updated = snap.model_copy(
        update={
            "ingestion_status": "ingested",
            "ingested_at": datetime.now(UTC).replace(microsecond=0),
        }
    )
    registry.snapshots = [updated if s is snap else s for s in registry.snapshots]
    save_registry(data_root, registry)
