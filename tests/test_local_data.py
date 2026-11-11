"""LOCAL DATA integration checks against the real files in data/raw.

Marked ``local_data`` and skipped automatically when the raw files are absent (CI).
They assert provenance and internal consistency, not hard-coded research results.
Run only these with:  uv run pytest -m local_data
"""

from pathlib import Path

import pytest

from compassio_ml.audit.loaders import SourceData
from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import DataLayout
from compassio_ml.data.manifest_io import manifest_path, validate_manifest

ROOT = Path(__file__).resolve().parents[1] / "data"
LAYOUT = DataLayout(ROOT)
HAS_RAW = LAYOUT.raw.is_dir() and any(
    p.is_file() and p.name != "README.md" for p in LAYOUT.raw.rglob("*")
)

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not HAS_RAW, reason="real source files not present in data/raw"),
]


def test_inventory_accepts_every_raw_file() -> None:
    inventory = build_inventory(LAYOUT)

    assert [r.relpath for r in inventory.records if r.error] == []
    assert inventory.missing_critical_sources == ()


@pytest.mark.skipif(not manifest_path(LAYOUT).is_file(), reason="manifest not written yet")
def test_committed_manifest_matches_raw_files() -> None:
    report = validate_manifest(LAYOUT, build_inventory(LAYOUT))

    assert report.ok, report.errors


def test_research_rows_are_a_subset_of_aiddata() -> None:
    data = SourceData(LAYOUT)
    research_ids = set(data.research_climate["AidData_Record_ID"])
    aiddata_ids = set(data.aiddata["AidData Record ID"])

    assert research_ids <= aiddata_ids
    assert data.research_climate["AidData_Record_ID"].is_unique
