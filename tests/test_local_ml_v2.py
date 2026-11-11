"""LOCAL DATA checks for ML v2 (Task 006-ML and its review gate).

Skipped unless ``COMPASSIO_DATA_ROOT`` points at the original project's data directory and v2
retrievals exist under the v2 output root. Verifies integrity and isolation only; trains and
evaluates nothing, and never reads sealed labels.
"""

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from compassio_ml.external.baseline import verify_baseline
from compassio_ml.external.development import (
    load_aiddata_development_ids,
    load_development_pool,
)
from compassio_ml.external.partition import (
    DEVELOPMENT_PARTITIONS,
    RESTRICTED,
    check_pool_integrity,
)
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.registry import verify_retrieval
from compassio_ml.external.rights import load_rights
from compassio_ml.external.v1_inputs import load_v1_research

REPO = Path(__file__).resolve().parents[1]
PATHS = V2Paths.from_env(REPO) if os.environ.get("COMPASSIO_DATA_ROOT") else None
MANIFESTS = sorted(PATHS.external_raw.glob("*/*/retrieval_manifest.json")) if PATHS else []


def _builds() -> list[Path]:
    """Builds made with the current partition design (review-gate builds)."""
    if PATHS is None:
        return []
    out = []
    for manifest in sorted(PATHS.datasets.glob("v2build_*/build_manifest.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("inputs", {}).get("design_version") == "v2_partition_design_v2":
            out.append(manifest.parent)
    return out


BUILDS = _builds()

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not MANIFESTS, reason="COMPASSIO_DATA_ROOT or v2 retrievals not present"),
]
needs_build = pytest.mark.skipif(not BUILDS, reason="no review-gate build present")


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: "/".join(p.parts[-3:-1]))
def test_retrieved_files_match_their_manifests(manifest: Path) -> None:
    assert verify_retrieval(manifest.parent) == []


def test_v1_baseline_untouched() -> None:
    assert PATHS is not None
    report = verify_baseline(PATHS, load_model=False)

    assert report.ok, [c for c in report.checks if not c["ok"]]


@needs_build
@pytest.mark.parametrize("build", BUILDS, ids=lambda p: p.name)
def test_pool_invariants_hold_on_real_build(build: Path) -> None:
    membership = pd.read_parquet(build / "partition_membership.parquet")
    rights = load_rights(REPO / "configs" / "ml_rights_eligibility_v2.yaml")

    counts = check_pool_integrity(membership, rights.restricted_sources())

    assert counts["records_checked"] == len(membership)


@needs_build
@pytest.mark.parametrize("build", BUILDS, ids=lambda p: p.name)
def test_every_consumed_v1_test_record_is_excluded(build: Path) -> None:
    assert PATHS is not None
    v1 = load_v1_research(PATHS)
    consumed = set(v1.loc[v1["v1_consumed_test"], "candidate_id"])
    membership = pd.read_parquet(build / "partition_membership.parquet").set_index("candidate_id")

    assert consumed  # the v1 tests were consumed
    roles = membership.loc[sorted(consumed), "v2_partition"]
    assert not roles.isin(DEVELOPMENT_PARTITIONS | {"external_test_candidate"}).any()
    dev_ids = load_aiddata_development_ids(PATHS, build.name)
    assert not set(dev_ids["candidate_id"]) & consumed


@needs_build
@pytest.mark.parametrize("build", BUILDS, ids=lambda p: p.name)
def test_development_files_hold_no_sealed_or_restricted_records(build: Path) -> None:
    assert PATHS is not None
    pool = load_development_pool(PATHS, build.name)
    candidates = pd.read_parquet(build / "candidates.parquet")

    assert set(candidates["v2_partition"]) <= DEVELOPMENT_PARTITIONS
    assert not candidates["source_id"].isin(["worldbank_projects", "gcf_project_pages"]).any()
    assert len(pool) == len(candidates)
    restricted = pd.read_parquet(PATHS.restricted_reference / build.name / "records.parquet")
    assert set(restricted["v2_partition"]) <= {RESTRICTED}
    assert "gcf_project_pages" in set(restricted["source_id"])


@needs_build
@pytest.mark.parametrize("build", BUILDS, ids=lambda p: p.name)
def test_issued_worksheets_ready_and_unfilled(build: Path) -> None:
    from compassio_ml.external.worksheets import check_worksheets

    assert PATHS is not None
    if not (PATHS.labeling / build.name).is_dir():
        pytest.skip("no worksheets issued for this build")
    report = check_worksheets(PATHS, build)

    assert report["ready_for_reviewers"], report["errors"]
