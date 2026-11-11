"""LOCAL DATA checks for the C05 experiment run (real FCDO/EC cohort).

Skipped unless the cached run exists under data/ml_v2/challenges/c05/. Re-verifies the run's
hashes, re-derives the attack and detector metrics from the stored files and checks that no
canonical artifact changed. Trains nothing and never reads sealed evaluations.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from compassio_ml.challenges.c05.attack import poison_count
from compassio_ml.challenges.c05.batch import labelled_fingerprint
from compassio_ml.challenges.c05.config import config_sha256, load_config
from compassio_ml.challenges.c05.experiment import verify_run
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.plan import load_plan

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "c05_poison_quarantine.yaml"
RUN = REPO / "data" / "ml_v2" / "challenges" / "c05" / f"c05_{config_sha256(CONFIG)[:12]}"
PINNED = {
    "data/db/compassio_dev.sqlite": (
        "d2b39adda32914eb9059ea80792a1a77d8dea62aca0f6d55ed37b5c1114dd385"
    ),
    "models/compassio_ccrc_v1/model.joblib": (
        "53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656"
    ),
    "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550/model.joblib": (
        "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574"
    ),
}

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not (RUN / "manifest.json").is_file(), reason="C05 run not present"),
]


def _json(rel: str) -> Any:
    return json.loads((RUN / rel).read_text(encoding="utf-8"))


def _jsonl(rel: str) -> list[dict[str, Any]]:
    with (RUN / rel).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def test_run_files_match_their_manifest() -> None:
    assert verify_run(RUN) == []


def test_clean_batch_is_the_pinned_ml_v2_train_cohort() -> None:
    rows = _jsonl("batch_A_clean.jsonl")
    ids = np.array([r["record_id"] for r in rows])
    labels = np.array([r["label"] for r in rows])
    plan = load_plan(REPO / "configs" / "ml_v2_fast_experiment.yaml")
    assert labelled_fingerprint(ids, labels) == plan.inputs.memberships["train"].sha256
    assert len(rows) == 13_317 and int(labels.sum()) == 4_194
    assert {r["source_id"] for r in rows} == {"iati_fcdo", "iati_ec_intpa"}


@pytest.mark.parametrize("mode", ["uniform", "targeted_non_energy_positive"])
def test_exactly_five_percent_inverted_and_nothing_else_changed(mode: str) -> None:
    clean = {r["record_id"]: r for r in _jsonl("batch_A_clean.jsonl")}
    poisoned = _jsonl(f"batch_B_poisoned_{mode}.jsonl")
    oracle = _json(f"private_oracle/oracle_{mode}.json")
    changed = {
        p["record_id"] for p in poisoned if p["supplied_label"] != clean[p["record_id"]]["label"]
    }
    assert changed == set(oracle["flipped_ids"])
    assert len(changed) == poison_count(13_317, 0.05) == 666
    assert oracle["seed"] == load_config(CONFIG).attack.seed
    assert {p["record_id"] for p in poisoned} == set(clean)
    if mode == "targeted_non_energy_positive":
        assert all(clean[i]["label"] == 1 and clean[i]["non_energy"] for i in changed)


@pytest.mark.parametrize("mode", ["uniform", "targeted_non_energy_positive"])
def test_reported_detection_metrics_reproduce_from_stored_files(mode: str) -> None:
    summary = _json("summary.json")["attacks"][mode]
    report = _json(f"gate/{mode}_report.json")
    oracle = set(_json(f"private_oracle/oracle_{mode}.json")["flipped_ids"])
    quarantined = {
        r["record_id"] for r in report["flagged_records"] if r["status"] == "quarantined"
    }
    accepted = {r["record_id"] for r in _jsonl(f"batch_C_protected_{mode}.jsonl")}
    d = summary["detection"]
    assert len(quarantined & oracle) == d["detected_poison_true_positives"]
    assert len(quarantined - oracle) == d["false_positives"]
    assert len(oracle - quarantined) == d["false_negatives"]
    assert not (accepted & quarantined)  # quarantined records never reach training
    assert len(accepted) + len(quarantined) == 13_317
    assert summary["models"]["protected_after_quarantine"]["training_records"] == len(accepted)


def test_benchmark_is_the_development_validation_partition_only() -> None:
    rows = _jsonl("benchmark.jsonl")
    assert len(rows) == 2_550
    train_ids = {r["record_id"] for r in _jsonl("batch_A_clean.jsonl")}
    assert not train_ids & {r["record_id"] for r in rows}
    assert "DEVELOPMENT BENCHMARK" in _json("summary.json")["benchmark_label"]


@pytest.mark.parametrize("rel", sorted(PINNED))
def test_canonical_models_and_database_are_unchanged(rel: str) -> None:
    path = REPO / rel
    if not path.is_file():
        pytest.skip(f"{rel} not present")
    assert sha256_file(path) == PINNED[rel]


ADDENDUM_CONFIG = REPO / "configs" / "c05_hardening_addendum.yaml"
ADDENDUM = RUN.parent / f"addendum_{config_sha256(ADDENDUM_CONFIG)[:12]}"
needs_addendum = pytest.mark.skipif(
    not (ADDENDUM / "manifest.json").is_file(), reason="C05 addendum run not present"
)


@needs_addendum
def test_addendum_files_match_their_manifest_and_base_run() -> None:
    assert verify_run(ADDENDUM) == []
    manifest = json.loads((ADDENDUM / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["base_manifest_sha256"] == sha256_file(RUN / "manifest.json")


@needs_addendum
@pytest.mark.parametrize("mode", ["uniform", "targeted_non_energy_positive"])
@pytest.mark.parametrize("policy", ["hardened", "top_share"])
def test_addendum_policy_metrics_reproduce_from_gate_reports(mode: str, policy: str) -> None:
    summary = json.loads((ADDENDUM / "summary.json").read_text(encoding="utf-8"))
    report = json.loads((ADDENDUM / f"gate_{mode}_{policy}.json").read_text(encoding="utf-8"))
    oracle = set(_json(f"private_oracle/oracle_{mode}.json")["flipped_ids"])
    quarantined = {
        r["record_id"] for r in report["flagged_records"] if r["status"] == "quarantined"
    }
    d = summary["final_seed"]["attacks"][mode][policy]["detection"]
    assert len(quarantined & oracle) == d["detected_poison_true_positives"]
    assert len(quarantined - oracle) == d["false_positives"]
    assert (
        report["input_fingerprint"]
        == _json(f"private_oracle/oracle_{mode}.json")["poisoned_fingerprint"]
    )
    trained = summary["models"][f"{mode}|{policy}"]["training_records"]
    assert trained == report["counts"]["accepted"]["records"] == 13_317 - len(quarantined)


@needs_addendum
def test_deployed_policy_in_addendum_equals_the_base_run() -> None:
    summary = json.loads((ADDENDUM / "summary.json").read_text(encoding="utf-8"))
    base = _json("summary.json")
    for mode in ("uniform", "targeted_non_energy_positive"):
        a = summary["final_seed"]["attacks"][mode]["two_signal"]["detection"]
        b = base["attacks"][mode]["detection"]
        for key in ("detected_poison_true_positives", "false_positives", "false_negatives"):
            assert a[key] == b[key]
