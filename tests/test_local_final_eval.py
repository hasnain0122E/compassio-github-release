"""LOCAL DATA checks of the Task 005 final evaluation records and the internal release.

Skipped when the local final-evaluation outputs or release are absent. Verifies integrity, not
performance; no test partition is re-evaluated here.
"""

import json
import stat
from pathlib import Path

import pytest
import yaml

from compassio_ml.modeling.final_eval import PROTOCOLS, plan_sha256
from compassio_ml.modeling.frozen import sha256_file
from compassio_ml.modeling.release import MODEL_VERSION, ReleasedClassifier

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "configs" / "final_evaluation_v1.yaml"
FINAL = REPO / "experiments" / "final_evaluation_v1"
RELEASE = REPO / "models" / "compassio_ccrc_v1"
TRUSTED = REPO / "configs" / "trusted_model_releases.json"

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(
        not (FINAL / "primary" / "test_access.json").is_file(),
        reason="final evaluation outputs not present",
    ),
]


def test_plan_hash_matches_committed_checksum() -> None:
    recorded = (
        (REPO / "configs" / "final_evaluation_v1.sha256").read_text(encoding="utf-8").split()[0]
    )

    assert plan_sha256(PLAN) == recorded


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_each_protocol_accessed_once_and_outputs_untampered(protocol: str) -> None:
    record = json.loads((FINAL / protocol / "test_access.json").read_text(encoding="utf-8"))

    assert record["status"] == "completed"
    assert record["plan_sha256"] == plan_sha256(PLAN)
    for name, digest in record["output_sha256"].items():
        path = FINAL / protocol / name
        assert sha256_file(path) == digest, name
        assert not path.stat().st_mode & stat.S_IWRITE, f"{name} should be read-only"
    results = json.loads((FINAL / protocol / "results.json").read_text(encoding="utf-8"))
    plan = yaml.safe_load(PLAN.read_text(encoding="utf-8"))
    assert results["model"]["records"] == plan["protocols"][protocol]["expected_test_records"]
    assert results["model"]["threshold"] == plan["protocols"][protocol]["threshold"]


def test_pakistan_holdout_counts_are_internally_consistent() -> None:
    pk = json.loads((FINAL / "pakistan_holdout" / "results.json").read_text(encoding="utf-8"))
    conf = pk["pakistan_confusion"]

    assert conf["all"]["records"] == conf["energy"]["records"] + conf["non_energy"]["records"]
    assert conf["all"]["positives"] == conf["energy"]["positives"] + conf["non_energy"]["positives"]
    assert pk["train_records"] > 0


@pytest.mark.skipif(not RELEASE.is_dir(), reason="release not built")
def test_release_is_the_evaluated_primary_model_and_reloads_stably() -> None:
    manifest = json.loads((RELEASE / "release_manifest.json").read_text(encoding="utf-8"))
    primary = json.loads((FINAL / "primary" / "results.json").read_text(encoding="utf-8"))

    assert manifest["model_version"] == MODEL_VERSION
    assert manifest["model_fingerprint"] == primary["model_fingerprint"]
    assert manifest["evaluation_plan_sha256"] == plan_sha256(PLAN)
    a = ReleasedClassifier.load(RELEASE, TRUSTED).predict(
        "Example hydropower plant", "Example loan."
    )
    b = ReleasedClassifier.load(RELEASE, TRUSTED).predict(
        "Example hydropower plant", "Example loan."
    )
    assert a == b
