"""Validation tests for the manifest *format* (schema version 2).

The values below are deliberately obvious placeholders (``example_source``,
all-zero hashes) used only to exercise validation rules. They are not records of
any real source and must never be copied into data/manifests/.
"""

from datetime import UTC, date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from compassio_ml.data import RightsStatus, SourceManifest, SourceManifestEntry
from compassio_ml.data.formats import FileFormat

PLACEHOLDER_SHA256 = "0" * 64


def entry_fields(**overrides: Any) -> dict[str, Any]:
    source_id = overrides.get("source_id", "example_source")
    fields: dict[str, Any] = {
        "source_id": source_id,
        "original_filename": "example.csv",
        "file_relpath": f"raw/{source_id}/example.csv",
        "file_size_bytes": 10,
        "file_format": FileFormat.CSV,
        "publisher": "Example Publisher",
        "sha256": PLACEHOLDER_SHA256,
        "acquisition_date": date(2000, 1, 1),
        "inspected_at": datetime(2000, 1, 1, tzinfo=UTC),
        "unit_of_observation": "one row per example item",
    }
    fields.update(overrides)
    return fields


def test_minimal_entry_defaults_to_rights_not_reviewed() -> None:
    entry = SourceManifestEntry(**entry_fields())

    assert entry.rights_status is RightsStatus.NOT_REVIEWED
    assert entry.record_count_after_inspection is None
    assert entry.related_sources == ()
    assert entry.confirmed_facts == ()
    assert entry.assumptions == ()


@pytest.mark.parametrize(
    "status",
    [RightsStatus.PERMITTED, RightsStatus.PERMITTED_WITH_CONDITIONS, RightsStatus.RESTRICTED],
)
def test_rights_decision_without_evidence_rejected(status: RightsStatus) -> None:
    with pytest.raises(ValidationError, match="requires rights_evidence"):
        SourceManifestEntry(**entry_fields(rights_status=status))


def test_rights_decision_with_evidence_accepted() -> None:
    entry = SourceManifestEntry(
        **entry_fields(
            rights_status=RightsStatus.PERMITTED_WITH_CONDITIONS,
            rights_evidence="License page reviewed 2000-01-01: attribution required.",
        )
    )

    assert entry.rights_status is RightsStatus.PERMITTED_WITH_CONDITIONS


@pytest.mark.parametrize(
    "sha256",
    ["", "0" * 63, "0" * 65, "G" * 64, "A" * 64],  # uppercase rejected: digests are lowercase
)
def test_invalid_sha256_rejected(sha256: str) -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(sha256=sha256))


@pytest.mark.parametrize("source_id", ["Example", "has space", "trailing_", "_leading", "a-b"])
def test_invalid_source_id_rejected(source_id: str) -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(source_id=source_id))


def test_negative_record_count_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(record_count_after_inspection=-1))


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(verified=True))


def test_naive_inspection_timestamp_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(inspected_at=datetime(2000, 1, 1)))


@pytest.mark.parametrize(
    "relpath",
    ["raw/other_source/example.csv", "raw/example_source/renamed.csv", "data/example.csv"],
)
def test_file_path_must_match_source_and_filename(relpath: str) -> None:
    with pytest.raises(ValidationError):
        SourceManifestEntry(**entry_fields(file_relpath=relpath))


def test_statement_cannot_be_both_fact_and_assumption() -> None:
    with pytest.raises(ValidationError, match="both confirmed and assumed"):
        SourceManifestEntry(
            **entry_fields(confirmed_facts=("same claim",), assumptions=("same claim",))
        )


def test_entry_cannot_relate_to_itself() -> None:
    with pytest.raises(ValidationError, match="own source_id"):
        SourceManifestEntry(**entry_fields(related_sources=("example_source",)))


def test_manifest_rejects_duplicate_source_ids() -> None:
    entry = SourceManifestEntry(**entry_fields())

    with pytest.raises(ValidationError, match="duplicate source_id values: example_source"):
        SourceManifest(entries=(entry, entry))


def test_manifest_rejects_same_file_registered_twice() -> None:
    first = SourceManifestEntry(**entry_fields())
    second = SourceManifestEntry(**entry_fields(source_id="example_other"))

    with pytest.raises(ValidationError, match="registered twice"):
        SourceManifest(entries=(first, second))


def test_manifest_round_trips_through_json() -> None:
    manifest = SourceManifest(
        entries=(
            SourceManifestEntry(**entry_fields()),
            SourceManifestEntry(
                **entry_fields(
                    source_id="example_other",
                    sha256="1" * 64,
                    related_sources=("example_source",),
                )
            ),
        )
    )

    restored = SourceManifest.model_validate_json(manifest.model_dump_json())

    assert restored == manifest


def test_schema_version_1_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SourceManifest.model_validate({"schema_version": 1, "entries": []})


def test_empty_manifest_is_valid() -> None:
    assert SourceManifest().entries == ()
