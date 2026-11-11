"""Inventory discovery and manifest write/validate over an ARTIFICIAL data root."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compassio_ml.data.formats import FileFormat
from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import DataLayout
from compassio_ml.data.manifest import RightsStatus
from compassio_ml.data.manifest_io import (
    build_manifest,
    manifest_path,
    validate_manifest,
    write_manifest,
)
from compassio_ml.integrity import sha256_file

MakeXlsx = Callable[[str, dict[str, list[list[object]]]], Path]

NOW = datetime(2000, 1, 1, tzinfo=UTC)


@pytest.fixture
def layout(tmp_path: Path, make_xlsx: MakeXlsx) -> DataLayout:
    """Registered folder names holding tiny artificial files."""
    root = tmp_path / "data"
    raw = root / "raw"
    (raw / "gcf_projects").mkdir(parents=True)
    xlsx = make_xlsx("example.xlsx", {"Sheet 1": [["Ref #"], ["EX001"]]})
    (raw / "gcf_projects" / "example.xlsx").write_bytes(xlsx.read_bytes())
    (raw / "climate_project_explorer").mkdir()
    (raw / "climate_project_explorer" / "example.csv").write_text("a\n1\n", encoding="utf-8")
    (raw / "adb_pakistan").mkdir()
    (raw / "adb_pakistan" / "example.xml").write_text("<r/>", encoding="utf-8")
    (raw / "README.md").write_text("ignored", encoding="utf-8")
    return DataLayout(root)


def test_inventory_hashes_and_formats(layout: DataLayout) -> None:
    inventory = build_inventory(layout, now=NOW)

    by_source = {r.source_id: r for r in inventory.records}
    assert set(by_source) == {"gcf_projects", "climate_project_explorer", "adb_pakistan"}
    assert by_source["gcf_projects"].file_format is FileFormat.XLSX
    assert by_source["climate_project_explorer"].file_format is FileFormat.CSV
    assert by_source["adb_pakistan"].file_format is FileFormat.XML
    xml = layout.raw / "adb_pakistan" / "example.xml"
    assert by_source["adb_pakistan"].sha256 == sha256_file(xml)
    assert by_source["adb_pakistan"].relpath == "raw/adb_pakistan/example.xml"
    assert all(r.error is None for r in inventory.records)


def test_inventory_reports_missing_critical_sources(layout: DataLayout) -> None:
    inventory = build_inventory(layout, now=NOW)

    assert "research_paper" in inventory.missing_critical_sources
    assert "aiddata" in inventory.missing_critical_sources
    assert "gcf_projects" not in inventory.missing_critical_sources
    assert inventory.has_errors


def test_inventory_refuses_unsupported_and_misplaced_files(layout: DataLayout) -> None:
    (layout.raw / "gcf_readiness").mkdir()
    (layout.raw / "gcf_readiness" / "notes.txt").write_text("x", encoding="utf-8")
    (layout.raw / "loose.csv").write_text("a\n", encoding="utf-8")
    (layout.raw / "unregistered_source").mkdir()
    (layout.raw / "unregistered_source" / "x.csv").write_text("a\n", encoding="utf-8")
    (layout.raw / "gcf_countries").mkdir()
    (layout.raw / "gcf_countries" / "wrong.csv").write_text("a\n", encoding="utf-8")

    errors = {r.relpath: r.error for r in build_inventory(layout, now=NOW).records if r.error}

    assert "unsupported extension" in str(errors["raw/gcf_readiness/notes.txt"])
    assert "directly in data/raw" in str(errors["raw/loose.csv"])
    assert "not a registered source" in str(errors["raw/unregistered_source/x.csv"])
    assert "expected xlsx" in str(errors["raw/gcf_countries/wrong.csv"])


def test_inventory_detects_identical_files(layout: DataLayout) -> None:
    copy = layout.raw / "climate_project_explorer" / "example_copy.csv"
    copy.write_bytes((layout.raw / "climate_project_explorer" / "example.csv").read_bytes())

    inventory = build_inventory(layout, now=NOW)

    assert inventory.distinct_file_count == len(inventory.records) - 1
    assert inventory.duplicate_hash_groups == (
        (
            "raw/climate_project_explorer/example.csv",
            "raw/climate_project_explorer/example_copy.csv",
        ),
    )


def test_inventory_refuses_corrupt_zip(layout: DataLayout) -> None:
    (layout.raw / "research_paper").mkdir()
    (layout.raw / "research_paper" / "example.zip").write_bytes(b"PK\x03\x04truncated")

    record = next(
        r for r in build_inventory(layout, now=NOW).records if r.source_id == "research_paper"
    )

    assert record.file_format is FileFormat.ZIP
    assert record.error is not None and "ZIP" in record.error


def test_missing_raw_directory(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_inventory(DataLayout(tmp_path / "nowhere"))


def test_manifest_write_then_validate(layout: DataLayout) -> None:
    inventory = build_inventory(layout, now=NOW)
    manifest = build_manifest(inventory, {"gcf_projects": 1}, NOW)
    write_manifest(manifest, layout)

    report = validate_manifest(layout, inventory)

    assert report.ok, report.errors
    assert report.checked_entries == 3
    entry = next(e for e in manifest.entries if e.source_id == "gcf_projects")
    assert entry.rights_status is RightsStatus.NOT_REVIEWED
    assert entry.record_count_after_inspection == 1
    assert any("Acquisition date not recorded" in a for a in entry.assumptions)


def test_validate_detects_changed_raw_file(layout: DataLayout) -> None:
    inventory = build_inventory(layout, now=NOW)
    write_manifest(build_manifest(inventory, {}, NOW), layout)
    (layout.raw / "adb_pakistan" / "example.xml").write_text("<changed/>", encoding="utf-8")

    report = validate_manifest(layout)

    assert not report.ok
    assert any("sha256" in e and "adb_pakistan" in e for e in report.errors)
    assert any("size" in e for e in report.errors)


def test_validate_detects_unregistered_and_missing_files(layout: DataLayout) -> None:
    inventory = build_inventory(layout, now=NOW)
    write_manifest(build_manifest(inventory, {}, NOW), layout)
    (layout.raw / "climate_project_explorer" / "example.csv").unlink()
    (layout.raw / "gcf_readiness").mkdir()
    extra = layout.raw / "gcf_readiness" / "example.xlsx"
    extra.write_bytes((layout.raw / "gcf_projects" / "example.xlsx").read_bytes() + b"")

    report = validate_manifest(layout, build_inventory(layout, now=NOW))

    assert any("file missing on disk" in e for e in report.errors)
    assert any("not in manifest" in e for e in report.errors)


def test_validate_without_manifest(layout: DataLayout) -> None:
    report = validate_manifest(layout)

    assert not report.ok
    assert "compassio-manifest write" in report.errors[0]
    assert not manifest_path(layout).exists()


def test_validate_reports_schema_errors(layout: DataLayout) -> None:
    path = manifest_path(layout)
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 2, "entries": [{"source_id": "Bad"}]}', encoding="utf-8")

    report = validate_manifest(layout)

    assert not report.ok
    assert "Schema validation failed" in report.errors[0]
