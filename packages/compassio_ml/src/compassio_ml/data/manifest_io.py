"""Write and validate ``data/manifests/source_manifest.json`` against files on disk."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import AnyUrl, ValidationError

from compassio_ml.data.inventory import Inventory
from compassio_ml.data.layout import DataLayout
from compassio_ml.data.manifest import RightsStatus, SourceManifest, SourceManifestEntry
from compassio_ml.data.sources import SOURCES_BY_ID
from compassio_ml.integrity import sha256_file

MANIFEST_FILENAME = "source_manifest.json"


def manifest_path(layout: DataLayout) -> Path:
    return layout.manifests / MANIFEST_FILENAME


def build_manifest(
    inventory: Inventory, record_counts: dict[str, int], inspected_at: datetime
) -> SourceManifest:
    """Combine curated registry metadata with measured inventory facts.

    Rights status is always ``not_reviewed``: licence statements found inside files
    are recorded as confirmed facts but a human review is still required.
    """
    entries = []
    for record in sorted(inventory.records, key=lambda r: r.source_id):
        if record.error is not None or record.file_format is None:
            continue
        definition = SOURCES_BY_ID[record.source_id]
        entries.append(
            SourceManifestEntry(
                source_id=record.source_id,
                original_filename=record.original_filename,
                file_relpath=record.relpath,
                file_size_bytes=record.size_bytes,
                file_format=record.file_format,
                publisher=definition.publisher,
                source_url=AnyUrl(definition.source_url) if definition.source_url else None,
                publisher_reference_url=(
                    AnyUrl(definition.reference_url) if definition.reference_url else None
                ),
                published_license_notes=definition.license_notes,
                sha256=record.sha256,
                acquisition_date=None,
                inspected_at=inspected_at,
                rights_status=RightsStatus.NOT_REVIEWED,
                unit_of_observation=definition.unit_of_observation,
                record_count_after_inspection=record_counts.get(record.source_id),
                related_sources=definition.related_sources,
                confirmed_facts=definition.confirmed_facts,
                assumptions=(
                    "Acquisition date not recorded by the developer (file timestamps are not "
                    "evidence of download date)",
                    *definition.assumptions,
                ),
                limitations=definition.limitations,
            )
        )
    return SourceManifest(entries=tuple(entries))


def write_manifest(manifest: SourceManifest, layout: DataLayout) -> Path:
    path = manifest_path(layout)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


@dataclass
class ValidationReport:
    manifest: Path
    errors: list[str] = field(default_factory=list)
    checked_entries: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_manifest(layout: DataLayout, inventory: Inventory | None = None) -> ValidationReport:
    """Check schema, on-disk hash/size for each entry, and that every raw file is registered."""
    path = manifest_path(layout)
    report = ValidationReport(manifest=path)
    if not path.is_file():
        report.errors.append(f"Manifest not found: {path}. Run `uv run compassio-manifest write`.")
        return report
    try:
        manifest = SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        report.errors.append(f"Schema validation failed:\n{exc}")
        return report

    for entry in manifest.entries:
        report.checked_entries += 1
        file_path = layout.root / entry.file_relpath
        if not file_path.is_file():
            report.errors.append(f"{entry.source_id}: file missing on disk: {entry.file_relpath}")
            continue
        size = file_path.stat().st_size
        if size != entry.file_size_bytes:
            report.errors.append(
                f"{entry.source_id}: size {size} != manifest {entry.file_size_bytes}"
            )
        digest = sha256_file(file_path)
        if digest != entry.sha256:
            report.errors.append(
                f"{entry.source_id}: sha256 {digest} != manifest {entry.sha256} "
                "(raw file changed or replaced)"
            )
        if entry.source_id not in SOURCES_BY_ID:
            report.errors.append(f"{entry.source_id}: not a registered source id")

    if inventory is not None:
        registered = {e.file_relpath for e in manifest.entries}
        for record in inventory.records:
            if record.error:
                report.errors.append(f"{record.relpath}: refused by inventory: {record.error}")
            elif record.relpath not in registered:
                report.errors.append(f"{record.relpath}: present in data/raw but not in manifest")
    return report
