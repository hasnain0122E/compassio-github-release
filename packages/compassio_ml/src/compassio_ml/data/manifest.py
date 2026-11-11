"""Typed model for the source-data provenance manifest (schema version 2).

The format is documented in ``docs/data/data_contracts.md``. One manifest file per
source lives at ``data/manifests/<source_id>.json``; entries are written only for
files physically present in ``data/raw/<source_id>/``.

Version 2 (Task 002, extended additively in Task 003 with optional
``publisher_reference_url`` and ``published_license_notes``) added: ``file_relpath``, ``file_size_bytes``, ``file_format``,
``inspected_at``, and the separation of ``confirmed_facts`` from ``assumptions``.
"""

from collections import Counter
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    model_validator,
)

from compassio_ml.data.formats import FileFormat

SCHEMA_VERSION: Literal[2] = 2

SourceId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$", max_length=80)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class RightsStatus(StrEnum):
    """License / redistribution review state of a source.

    ``not_reviewed`` is the default. A concluded decision (permitted,
    permitted with conditions, or restricted) requires written
    ``rights_evidence``, so rights can never be declared verified without it.
    """

    NOT_REVIEWED = "not_reviewed"
    UNDER_REVIEW = "under_review"
    PERMITTED = "permitted"
    PERMITTED_WITH_CONDITIONS = "permitted_with_conditions"
    RESTRICTED = "restricted"


_STATUSES_REQUIRING_EVIDENCE = frozenset(
    {RightsStatus.PERMITTED, RightsStatus.PERMITTED_WITH_CONDITIONS, RightsStatus.RESTRICTED}
)


class SourceManifestEntry(BaseModel):
    """Provenance record for one acquired source file."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    source_id: SourceId
    original_filename: NonEmptyStr
    file_relpath: Annotated[str, Field(pattern=r"^raw/[^\\]+$")]
    file_size_bytes: NonNegativeInt
    file_format: FileFormat
    publisher: NonEmptyStr
    source_url: AnyUrl | None = None
    # Publisher landing/record page; NOT the exact download location (Task 003 addition).
    publisher_reference_url: AnyUrl | None = None
    sha256: Sha256Hex
    acquisition_date: date | None = None
    inspected_at: AwareDatetime
    source_publication_date: date | None = None
    rights_status: RightsStatus = RightsStatus.NOT_REVIEWED
    rights_evidence: str | None = None
    # Licence/terms text noted for later human review; never an authorization.
    published_license_notes: str | None = None
    unit_of_observation: NonEmptyStr
    record_count_after_inspection: NonNegativeInt | None = None
    related_sources: tuple[SourceId, ...] = ()
    known_duplicates_notes: str | None = None
    confirmed_facts: tuple[NonEmptyStr, ...] = ()
    assumptions: tuple[NonEmptyStr, ...] = ()
    limitations: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def _rights_decisions_need_evidence(self) -> Self:
        if self.rights_status in _STATUSES_REQUIRING_EVIDENCE and not self.rights_evidence:
            raise ValueError(
                f"rights_status '{self.rights_status}' requires rights_evidence "
                "(for example the license URL and the date it was reviewed)"
            )
        return self

    @model_validator(mode="after")
    def _not_related_to_itself(self) -> Self:
        if self.source_id in self.related_sources:
            raise ValueError("related_sources must not include the entry's own source_id")
        return self

    @model_validator(mode="after")
    def _path_matches_source(self) -> Self:
        expected_prefix = f"raw/{self.source_id}/"
        if not self.file_relpath.startswith(expected_prefix):
            raise ValueError(f"file_relpath must start with {expected_prefix!r}")
        if not self.file_relpath.endswith("/" + self.original_filename):
            raise ValueError("file_relpath must end with original_filename")
        return self

    @model_validator(mode="after")
    def _facts_and_assumptions_disjoint(self) -> Self:
        overlap = set(self.confirmed_facts) & set(self.assumptions)
        if overlap:
            raise ValueError(f"statements cannot be both confirmed and assumed: {sorted(overlap)}")
        return self


class SourceManifest(BaseModel):
    """A collection of source manifest entries with unique ``source_id`` values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[2] = SCHEMA_VERSION
    entries: tuple[SourceManifestEntry, ...] = ()

    @model_validator(mode="after")
    def _unique_source_ids(self) -> Self:
        counts = Counter(entry.source_id for entry in self.entries)
        duplicates = sorted(source_id for source_id, n in counts.items() if n > 1)
        if duplicates:
            raise ValueError(f"duplicate source_id values: {', '.join(duplicates)}")
        return self

    @model_validator(mode="after")
    def _unique_hashes(self) -> Self:
        counts = Counter(entry.sha256 for entry in self.entries)
        duplicates = sorted(sha for sha, n in counts.items() if n > 1)
        if duplicates:
            raise ValueError(f"the same file (sha256) is registered twice: {duplicates}")
        return self
