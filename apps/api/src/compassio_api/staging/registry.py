"""Backend source registry: provenance for files the backend downloads itself.

Independent of the canonical nine-source manifest (``data/manifests/source_manifest.json``,
owned by the ML track). Files live under ``data/raw_db/<backend_source_id>/<UTC stamp>/`` and are
never placed in ``data/raw/``, so ML inventory/manifest tools never see them.

* ``data/raw_db/registry.json`` -- the operational registry (local, git-ignored with the data).
* ``data/manifests/backend_source_registry.json`` -- the same metadata, Git-tracked. It holds
  only provenance (URLs, timestamps, HTTP metadata, hashes, rights notes), never records.

Both are validated to be identical. This is a *staging* registry, to be reconciled with the
canonical manifest later (docs/data/backend_source_registry.md).
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from compassio_ml.integrity.hashing import sha256_file

REGISTRY_SCHEMA = "compassio-backend-source-registry/1"
LOCAL_REGISTRY = "registry.json"
TRACKED_REGISTRY = Path("manifests") / "backend_source_registry.json"
IGNORED_NAMES = frozenset({LOCAL_REGISTRY, "README.md"})

RightsStatus = Literal["not_reviewed", "under_review"]  # clearance needs a canonical review


@dataclass(frozen=True, slots=True)
class BackendSourceDefinition:
    backend_source_id: str
    publisher: str
    description: str
    landing_url: str
    retrieval_url: str
    file_format: Literal["json"]
    unit_of_observation: str
    attribution_notes: str
    max_bytes: int


BACKEND_SOURCES: dict[str, BackendSourceDefinition] = {
    "gcf_api_projects": BackendSourceDefinition(
        backend_source_id="gcf_api_projects",
        publisher="Green Climate Fund (GCF) Open Data Library API",
        description=(
            "All GCF funded projects (FP/SAP) as structured JSON: approval date, status, "
            "countries with per-country financing (currency stated), funding by source and "
            "instrument (currency stated), disbursements, entities, official project URL."
        ),
        landing_url="https://data.greenclimate.fund/",
        retrieval_url="https://api.gcfund.org/v1/projects",
        file_format="json",
        unit_of_observation="one GCF funded project (ApprovedRef, e.g. FP085)",
        attribution_notes=(
            "GCF website terms (checked 2026-11-09 for Task 004.5): private study, research and "
            "non-commercial use; commercial use or redistribution needs prior written consent; "
            "attribute 'First published by the Green Climate Fund' with a link. The site's "
            "robots.txt Content-Signal states ai-train=no: do not use for model training. "
            "Not reviewed for redistribution."
        ),
        max_bytes=60_000_000,
    ),
}


class SnapshotEntry(BaseModel):
    """One downloaded, immutable snapshot of a backend source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend_source_id: str
    snapshot_id: str = Field(pattern=r"^\d{8}T\d{6}Z$")
    publisher: str
    description: str
    landing_url: str
    retrieval_url: str
    retrieved_at: AwareDatetime
    http_status: int
    http_metadata: dict[str, str]
    original_filename: str
    stored_relpath: str  # relative to data/raw_db
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=1)
    file_format: str
    source_update_date: str | None  # only if the publisher states it; never inferred
    source_update_date_note: str
    rights_status: RightsStatus = "not_reviewed"
    attribution_notes: str
    unit_of_observation: str
    ingestion_status: Literal["registered", "validated", "ingested"] = "registered"
    ingested_at: AwareDatetime | None = None


class BackendRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = REGISTRY_SCHEMA
    snapshots: list[SnapshotEntry] = Field(default_factory=list)

    def latest(self, backend_source_id: str) -> SnapshotEntry | None:
        matching = [s for s in self.snapshots if s.backend_source_id == backend_source_id]
        return max(matching, key=lambda s: s.snapshot_id) if matching else None


class RegistryError(RuntimeError):
    pass


def raw_db_dir(data_root: Path) -> Path:
    return data_root / "raw_db"


def load_registry(data_root: Path) -> BackendRegistry:
    path = raw_db_dir(data_root) / LOCAL_REGISTRY
    if not path.is_file():
        return BackendRegistry()
    return BackendRegistry.model_validate_json(path.read_text(encoding="utf-8"))


def _serialise(registry: BackendRegistry) -> str:
    return json.dumps(registry.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def save_registry(data_root: Path, registry: BackendRegistry) -> None:
    """Write the local registry and its Git-tracked metadata copy (identical content)."""
    text = _serialise(registry)
    local = raw_db_dir(data_root) / LOCAL_REGISTRY
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text, encoding="utf-8", newline="\n")
    tracked = data_root / TRACKED_REGISTRY
    tracked.parent.mkdir(parents=True, exist_ok=True)
    tracked.write_text(text, encoding="utf-8", newline="\n")


@dataclass
class RegistryReport:
    checked: int
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_registry(data_root: Path) -> RegistryReport:
    """Reject missing, changed or unregistered backend source files and registry drift."""
    errors: list[str] = []
    base = raw_db_dir(data_root)
    registry = load_registry(data_root)
    tracked = data_root / TRACKED_REGISTRY
    if registry.snapshots or tracked.is_file():
        if not tracked.is_file():
            errors.append(f"tracked registry missing: {tracked}")
        elif tracked.read_text(encoding="utf-8") != _serialise(registry):
            errors.append("local registry and tracked registry differ")
    registered: set[Path] = set()
    seen: set[tuple[str, str]] = set()
    for entry in registry.snapshots:
        key = (entry.backend_source_id, entry.snapshot_id)
        if key in seen:
            errors.append(f"duplicate snapshot {key}")
        seen.add(key)
        if entry.backend_source_id not in BACKEND_SOURCES:
            errors.append(f"{entry.backend_source_id}: not a defined backend source")
        path = (base / entry.stored_relpath).resolve()
        registered.add(path)
        if not path.is_file():
            errors.append(f"{entry.stored_relpath}: registered file is missing")
            continue
        if path.stat().st_size != entry.size_bytes:
            errors.append(f"{entry.stored_relpath}: size changed")
        if sha256_file(path) != entry.sha256:
            errors.append(f"{entry.stored_relpath}: sha256 changed (snapshot modified)")
    if base.is_dir():
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if path.name in IGNORED_NAMES and path.parent == base:
                continue
            if path.name == "http_headers.json":
                continue  # provenance sidecar, recorded in http_metadata
            if path.resolve() not in registered:
                errors.append(f"{path.relative_to(base).as_posix()}: unregistered file")
    return RegistryReport(checked=len(registry.snapshots), errors=errors)


def snapshot_id_for(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")
