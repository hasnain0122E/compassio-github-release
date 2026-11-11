"""Versioned external-source registry (``configs/external_sources_v2.yaml``) and retrieval runs.

The registry is curated, human-reviewable metadata. As in ``compassio_ml.data.sources``,
``confirmed_facts`` were observed in this project, ``assumptions`` were not, and measured values
(hashes, sizes, counts) are never stored in the registry: they come from retrieval manifests
and inspection reports.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from compassio_ml.external.fetch import FetchError, Retrieval, SafeFetcher
from compassio_ml.external.paths import V2Paths

REGISTRY_VERSION = "external_sources_v2"
DEFAULT_REGISTRY = Path("configs") / "external_sources_v2.yaml"


class AccessStatus(StrEnum):
    OPEN = "open"
    CREDENTIAL_REQUIRED = "credential_required"
    BLOCKED_AUTOMATED_ACCESS = "blocked_automated_access"
    MANUAL_DOWNLOAD_REQUIRED = "manual_download_required"


class LabelCategory(StrEnum):
    """Task 006-ML label categories. They are NOT interchangeable."""

    RESEARCHER_RIO = "A_researcher_rio"
    DONOR_RIO = "B_donor_reported_rio"
    GCF_CLASSIFICATION = "C_gcf_classification"
    WB_CLIMATE_INDICATOR = "D_world_bank_climate_indicator"
    HUMAN_REVIEWED = "E_human_reviewed"
    NONE = "none"


class ExternalSourceDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    publisher: str
    title: str
    authoritative_url: str
    access_status: AccessStatus
    access_notes: str
    dataset_version: str
    unit_of_observation: str
    record_identifier: str
    country_field: str
    date_fields: dict[str, str]
    title_field: str
    description_fields: list[str]
    proposal_stage_text: str
    label_category: LabelCategory
    label_definition: str
    label_authority: str
    sector_field: str
    financial_units: str
    relationships: str
    legal_terms_url: str | None
    legal_terms_evidence: str
    rights_status: str = "not_reviewed"
    retrieval_limits: dict[str, int | float] = Field(default_factory=dict)
    confirmed_facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("rights_status")
    @classmethod
    def _rights_not_cleared_without_review(cls, value: str) -> str:
        if value != "not_reviewed":
            raise ValueError(
                "rights_status may only change after a recorded human licence review; "
                "the external registry keeps 'not_reviewed'"
            )
        return value


class ExternalRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_version: str
    sources: list[ExternalSourceDefinition]

    @field_validator("registry_version")
    @classmethod
    def _version(cls, value: str) -> str:
        if value != REGISTRY_VERSION:
            raise ValueError(f"expected registry_version {REGISTRY_VERSION}")
        return value

    @field_validator("sources")
    @classmethod
    def _unique(cls, value: list[ExternalSourceDefinition]) -> list[ExternalSourceDefinition]:
        ids = [s.source_id for s in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate source_id in external registry")
        return value

    def get(self, source_id: str) -> ExternalSourceDefinition:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(f"Unknown external source: {source_id}")


def load_registry(path: Path = DEFAULT_REGISTRY) -> ExternalRegistry:
    with path.open(encoding="utf-8") as handle:
        data: Any = yaml.safe_load(handle)
    return ExternalRegistry.model_validate(data)


def new_retrieval_id(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")


@dataclass
class RetrievalRun:
    """One acquisition run for one source. Files are never overwritten or edited later."""

    paths: V2Paths
    source: ExternalSourceDefinition
    fetcher: SafeFetcher
    retrieval_id: str = field(default_factory=new_retrieval_id)
    files: list[dict[str, object]] = field(default_factory=list)
    failures: list[dict[str, object]] = field(default_factory=list)
    parameters: dict[str, object] = field(default_factory=dict)

    @property
    def directory(self) -> Path:
        return self.paths.external_raw / self.source.source_id / self.retrieval_id

    def start(self) -> Path:
        directory = self.paths.writable(self.directory)
        if directory.exists():
            raise FileExistsError(f"Retrieval directory already exists: {directory}")
        directory.mkdir(parents=True)
        return directory

    def fetch(
        self, url: str, filename: str, *, max_bytes: int | None = None, role: str = "data"
    ) -> Retrieval | None:
        dest = self.paths.writable(self.directory / filename)
        try:
            retrieval = self.fetcher.fetch(url, dest, max_bytes=max_bytes)
        except FetchError as exc:
            self.failures.append(
                {
                    "url": url,
                    "file": filename,
                    "role": role,
                    "error": str(exc),
                    "http_status": exc.status,
                }
            )
            return None
        record = retrieval.as_record(self.directory)
        record["role"] = role
        self.files.append(record)
        return retrieval

    def finish(self, notes: list[str] | None = None) -> Path:
        manifest = {
            "registry_version": REGISTRY_VERSION,
            "source_id": self.source.source_id,
            "publisher": self.source.publisher,
            "retrieval_id": self.retrieval_id,
            "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "user_agent": self.fetcher.user_agent,
            "min_interval_s": self.fetcher.limits.min_interval_s,
            "parameters": self.parameters,
            "rights_status": self.source.rights_status,
            "legal_terms_evidence": self.source.legal_terms_evidence,
            "files": self.files,
            "failures": self.failures,
            "notes": notes or [],
        }
        path = self.paths.writable(self.directory / "retrieval_manifest.json")
        with path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return path


def latest_retrieval(paths: V2Paths, source_id: str) -> Path:
    """Most recent completed retrieval directory (has a manifest) for a source."""
    base = paths.external_raw / source_id
    done = sorted(p.parent for p in base.glob("*/retrieval_manifest.json"))
    if not done:
        raise FileNotFoundError(
            f"No completed retrieval for {source_id} under {base}. Run `compassio-v2 acquire "
            f"{source_id}` first."
        )
    return done[-1]


def read_retrieval_manifest(directory: Path) -> dict[str, Any]:
    with (directory / "retrieval_manifest.json").open(encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)
    return data


def verify_retrieval(directory: Path) -> list[str]:
    """Re-hash every file listed in a retrieval manifest; return error strings."""
    from compassio_ml.integrity import sha256_file

    errors: list[str] = []
    manifest = read_retrieval_manifest(directory)
    for entry in manifest["files"]:
        path = directory / str(entry["file"])
        if not path.is_file():
            errors.append(f"missing: {path}")
        elif sha256_file(path) != entry["sha256"]:
            errors.append(f"hash mismatch: {path}")
    return errors
