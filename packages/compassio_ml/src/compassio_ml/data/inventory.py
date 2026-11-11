"""Discover, hash and format-check every file under ``data/raw/<source_id>/``.

Read-only: files are opened only for hashing and signature sniffing.
"""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from compassio_ml.data.formats import FileFormat, UnsupportedFormatError, detect_format
from compassio_ml.data.layout import DataLayout
from compassio_ml.data.sources import SOURCES_BY_ID
from compassio_ml.integrity import sha256_file
from compassio_ml.safety.archive import (
    ArchiveLimits,
    CorruptArchiveError,
    UnsafeArchiveError,
    inspect_zip,
)

IGNORED_FILENAMES = frozenset({"README.md", ".gitkeep", ".DS_Store", "Thumbs.db", "desktop.ini"})


class ArchiveMemberRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    uncompressed_bytes: int
    compressed_bytes: int
    is_junk: bool


class InventoryRecord(BaseModel):
    """One discovered file. ``error`` is set when the file is refused."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    registered_source: bool
    relpath: str
    original_filename: str
    size_bytes: int
    sha256: str
    file_format: FileFormat | None
    archive_members: tuple[ArchiveMemberRecord, ...] = ()
    error: str | None = None


class Inventory(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_root: str
    inspected_at: datetime
    records: tuple[InventoryRecord, ...]
    missing_critical_sources: tuple[str, ...]
    missing_optional_sources: tuple[str, ...]
    duplicate_hash_groups: tuple[tuple[str, ...], ...]

    @property
    def distinct_file_count(self) -> int:
        return len({r.sha256 for r in self.records})

    @property
    def has_errors(self) -> bool:
        return any(r.error for r in self.records) or bool(self.missing_critical_sources)


def _inspect_file(path: Path, layout: DataLayout, limits: ArchiveLimits) -> InventoryRecord:
    source_id = path.parent.name
    relpath = path.relative_to(layout.root).as_posix()
    digest = sha256_file(path)
    size = path.stat().st_size
    def record(
        file_format: FileFormat | None,
        error: str | None,
        members: tuple[ArchiveMemberRecord, ...] = (),
    ) -> InventoryRecord:
        return InventoryRecord(
            source_id=source_id,
            registered_source=source_id in SOURCES_BY_ID,
            relpath=relpath,
            original_filename=path.name,
            size_bytes=size,
            sha256=digest,
            file_format=file_format,
            archive_members=members,
            error=error,
        )

    try:
        file_format = detect_format(path)
    except UnsupportedFormatError as exc:
        return record(None, str(exc))

    members: tuple[ArchiveMemberRecord, ...] = ()
    error: str | None = None
    if file_format in (FileFormat.ZIP, FileFormat.XLSX):
        try:
            found = inspect_zip(path, limits)
        except (CorruptArchiveError, UnsafeArchiveError) as exc:
            error = str(exc)
        else:
            if file_format is FileFormat.ZIP:
                members = tuple(
                    ArchiveMemberRecord(
                        name=m.name,
                        uncompressed_bytes=m.uncompressed_bytes,
                        compressed_bytes=m.compressed_bytes,
                        is_junk=m.is_junk,
                    )
                    for m in found
                    if not m.is_dir
                )
    expected = SOURCES_BY_ID.get(source_id)
    if error is None and expected is not None and expected.expected_format is not file_format:
        error = (
            f"{path.name}: expected {expected.expected_format.value} for source "
            f"'{source_id}', found {file_format.value}"
        )
    if error is None and expected is None:
        error = f"Folder '{source_id}' is not a registered source (see compassio_ml.data.sources)"
    return record(file_format, error, members)


def build_inventory(
    layout: DataLayout,
    *,
    limits: ArchiveLimits | None = None,
    now: datetime | None = None,
) -> Inventory:
    """Inventory ``layout.raw``. Raises ``MissingSourceDataError``-style errors only via
    the returned record list; a missing raw directory raises ``FileNotFoundError``."""
    if not layout.raw.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {layout.raw}")
    lim = limits or ArchiveLimits()
    records: list[InventoryRecord] = []
    for path in sorted(layout.raw.rglob("*")):
        if not path.is_file() or path.name in IGNORED_FILENAMES:
            continue
        if path.parent == layout.raw:
            records.append(
                InventoryRecord(
                    source_id="",
                    registered_source=False,
                    relpath=path.relative_to(layout.root).as_posix(),
                    original_filename=path.name,
                    size_bytes=path.stat().st_size,
                    sha256=sha256_file(path),
                    file_format=None,
                    error="File placed directly in data/raw/; move it into data/raw/<source_id>/",
                )
            )
            continue
        records.append(_inspect_file(path, layout, lim))

    present = {r.source_id for r in records if r.error is None}
    missing_critical = tuple(
        sid for sid, s in SOURCES_BY_ID.items() if s.critical and sid not in present
    )
    missing_optional = tuple(
        sid for sid, s in SOURCES_BY_ID.items() if not s.critical and sid not in present
    )
    by_hash = Counter(r.sha256 for r in records)
    dup_groups = tuple(
        tuple(sorted(r.relpath for r in records if r.sha256 == sha))
        for sha, n in sorted(by_hash.items())
        if n > 1
    )
    return Inventory(
        data_root=str(layout.root),
        inspected_at=now or datetime.now(UTC),
        records=tuple(records),
        missing_critical_sources=missing_critical,
        missing_optional_sources=missing_optional,
        duplicate_hash_groups=dup_groups,
    )
