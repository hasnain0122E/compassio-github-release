"""C05 poisoned-batch quarantine: fast regression tests on ARTIFICIAL example_* text.

The fixture vocabulary is invented (``example_*`` tokens); it exercises logic only and says
nothing about real project data. Real-data checks live in tests/test_local_c05.py.
"""

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from compassio_ml.challenges.c05 import detector as detector_module
from compassio_ml.challenges.c05.attack import inject_label_flips, poison_count
from compassio_ml.challenges.c05.batch import SuppliedBatch
from compassio_ml.challenges.c05.config import C05Config, load_config
from compassio_ml.challenges.c05.detector import assess
from compassio_ml.challenges.c05.experiment import detection_metrics
from compassio_ml.challenges.c05.gate import (
    AcceptedBatch,
    GateBypassError,
    quarantine_gate,
)
from compassio_ml.challenges.c05.train import Baseline, fit_downstream

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "packages" / "compassio_ml" / "src" / "compassio_ml" / "challenges" / "c05"
POS = [f"example_climate_{i}" for i in range(12)]
NEG = [f"example_other_{i}" for i in range(12)]
SHARED = [f"example_common_{i}" for i in range(20)]


def example_batch(n: int = 600, seed: int = 0, positive_share: float = 0.35) -> SuppliedBatch:
    rng = np.random.default_rng(seed)
    labels = (rng.random(n) < positive_share).astype(int)
    texts = []
    for i, y in enumerate(labels):
        topic = POS if y == 1 else NEG
        words = list(rng.choice(topic, 6)) + list(rng.choice(SHARED, 4))
        texts.append(f"example_record_{i} " + " ".join(words))
    groups = np.array([f"example_group_{i // 3}" for i in range(n)])  # groups of 3
    sources = np.array(["example_pub_a" if i % 4 else "example_pub_b" for i in range(n)])
    return SuppliedBatch.create(
        np.array([f"example:{i}" for i in range(n)]), np.array(texts), labels, groups, sources
    )


def small_config() -> C05Config:
    cfg = load_config(REPO / "configs" / "c05_poison_quarantine.yaml")
    det = cfg.detector.model_copy(
        update={
            "n_splits": 3,
            "min_class_support": 10,
            "knn": cfg.detector.knn.model_copy(update={"k": 7}),
            "text_model": cfg.detector.text_model.model_copy(
                update={"features": {**cfg.detector.text_model.features, "min_df": 1}}
            ),
        }
    )
    ds = cfg.downstream.model_copy(update={"features": "word", "n_splits": 3})
    return cfg.model_copy(update={"detector": det, "downstream": ds})


SPECS: dict[str, dict[str, Any]] = {
    "word": {
        "analyzer": "word",
        "ngram_range": [1, 1],
        "min_df": 1,
        "max_df": 1.0,
        "max_features": 5000,
        "sublinear_tf": True,
    }
}


# ----------------------------------------------------------------------------- attack
def test_exactly_five_percent_of_labels_are_inverted() -> None:
    assert poison_count(13_317, 0.05) == 666  # the real TRAIN batch
    batch = example_batch(1_000)
    poisoned, oracle = inject_label_flips(batch, 0.05, 11, "uniform")
    changed = batch.labels != poisoned.labels
    assert oracle.count == int(changed.sum()) == 50
    assert set(batch.ids[changed]) == set(oracle.flipped_ids)
    assert np.array_equal(poisoned.labels[changed], 1 - batch.labels[changed])


def test_original_records_are_never_modified() -> None:
    batch = example_batch()
    before = (batch.labels.copy(), batch.texts.copy(), batch.ids.copy(), batch.fingerprint())
    inject_label_flips(batch, 0.05, 1, "uniform")
    assert np.array_equal(batch.labels, before[0]) and np.array_equal(batch.texts, before[1])
    assert np.array_equal(batch.ids, before[2]) and batch.fingerprint() == before[3]
    with pytest.raises(ValueError):
        batch.labels[0] = 1 - batch.labels[0]  # read-only arrays


def test_attack_is_deterministic_per_seed() -> None:
    batch = example_batch()
    a = inject_label_flips(batch, 0.05, 42, "uniform")[1]
    b = inject_label_flips(batch, 0.05, 42, "uniform")[1]
    c = inject_label_flips(batch, 0.05, 43, "uniform")[1]
    assert a.flipped_ids == b.flipped_ids and a.poisoned_fingerprint == b.poisoned_fingerprint
    assert a.flipped_ids != c.flipped_ids


def test_targeted_attack_flips_only_climate_positive_non_energy_records() -> None:
    batch = example_batch()
    non_energy = np.arange(len(batch)) % 5 != 0
    poisoned, oracle = inject_label_flips(
        batch, 0.05, 3, "targeted_non_energy_positive", non_energy
    )
    flipped = np.isin(batch.ids, oracle.flipped_ids)
    assert oracle.count == poison_count(len(batch), 0.05)
    assert (batch.labels[flipped] == 1).all() and (poisoned.labels[flipped] == 0).all()
    assert non_energy[flipped].all()


# ----------------------------------------------------------------------------- oracle isolation
@pytest.mark.parametrize("module", ["detector.py", "gate.py", "batch.py", "train.py"])
def test_detector_and_gate_never_import_the_attack_or_oracle(module: str) -> None:
    tree = ast.parse((PACKAGE / module).read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "compassio_ml.challenges.c05.attack" not in imported
    assert "PoisonOracle" not in names and "oracle" not in names


def test_gate_decisions_do_not_depend_on_the_oracle() -> None:
    cfg = small_config()
    poisoned, oracle_a = inject_label_flips(example_batch(), 0.05, 5, "uniform")
    # The gate receives only the supplied batch: same batch -> same decisions, whatever the
    # oracle says (here we only check the gate's signature and determinism).
    first = quarantine_gate(poisoned, cfg)
    second = quarantine_gate(poisoned, cfg)
    assert first.quarantined_ids == second.quarantined_ids
    assert list(quarantine_gate.__code__.co_varnames[:2]) == ["batch", "cfg"]
    assert oracle_a.count > 0


# ----------------------------------------------------------------------------- detector
def test_folds_are_group_aware() -> None:
    batch, _ = inject_label_flips(example_batch(), 0.05, 2, "uniform")
    result = assess(batch, small_config().detector)
    for group in set(batch.groups.tolist()):
        assert len(set(result.fold[batch.groups == group].tolist())) == 1


def test_vectoriser_is_fitted_on_training_folds_only(monkeypatch: pytest.MonkeyPatch) -> None:
    fitted: list[set[str]] = []
    original = detector_module._vectorizer

    def spy(spec: dict[str, object]) -> Any:
        vec = original(spec)
        fit = vec.fit_transform

        def recording(docs: Any, *a: Any, **k: Any) -> Any:
            fitted.append(set(map(str, docs)))
            return fit(docs, *a, **k)

        vec.fit_transform = recording
        return vec

    monkeypatch.setattr(detector_module, "_vectorizer", spy)
    batch = example_batch()
    result = assess(batch, small_config().detector)
    assert len(fitted) == 3
    for fold, docs in enumerate(fitted):
        held_out = set(batch.texts[result.fold == fold].tolist())
        assert held_out and not (held_out & docs)


def test_detector_finds_inverted_labels_better_than_chance() -> None:
    clean = example_batch(900, seed=4)
    poisoned, oracle = inject_label_flips(clean, 0.05, 9, "uniform")
    gate = quarantine_gate(poisoned, small_config())
    metrics = detection_metrics(
        poisoned.ids,
        gate.detector.status,
        gate.detector.suspicion,
        oracle,
        clean.labels,
        np.zeros(len(clean), dtype=bool),
    )
    assert metrics["detection_recall"] > 0.5
    assert metrics["detection_precision"] > 0.5
    assert metrics["false_quarantine_rate"] < 0.05


def test_flags_are_never_declared_proof_of_poisoning() -> None:
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 6, "uniform")
    gate = quarantine_gate(poisoned, small_config())
    assert set(gate.detector.status.tolist()) <= {
        "accepted",
        "quarantined",
        "insufficient_evidence",
    }
    assert "not proof" in gate.report["interpretation"]
    for record in gate.report["flagged_records"]:
        text = record["reason"].lower()
        assert "poison" not in text and "corrupt" not in text


def test_sparse_class_means_insufficient_evidence_not_quarantine() -> None:
    batch = example_batch(300, positive_share=0.02)  # ~6 positives
    gate = quarantine_gate(batch, small_config())
    assert not gate.quarantined_ids
    assert set(gate.detector.status.tolist()) == {"insufficient_evidence"}
    assert gate.report["notes"] and "min_class_support" in gate.report["notes"][0]


def test_sparse_publisher_falls_back_to_batch_thresholds() -> None:
    batch = example_batch(600)
    result = assess(batch, small_config().detector)
    # example_pub_b holds 150 records (~52 positives): enough; a tiny publisher would not be.
    tiny = SuppliedBatch.create(
        batch.ids,
        batch.texts,
        batch.labels,
        batch.groups,
        np.where(np.arange(600) < 6, "example_pub_tiny", batch.sources),
    )
    tiny_result = assess(tiny, small_config().detector)
    assert tiny_result.thresholds["example_pub_tiny"] == tiny_result.thresholds["__batch__"]
    assert result.thresholds["example_pub_b"] != result.thresholds["__batch__"]


def test_detector_is_reproducible() -> None:
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 8, "uniform")
    a = assess(poisoned, small_config().detector)
    b = assess(poisoned, small_config().detector)
    assert np.array_equal(a.status, b.status)
    assert np.allclose(a.p_positive, b.p_positive, equal_nan=True)


# ----------------------------------------------------------------------------- gate + training
def test_quarantine_happens_before_fitting(monkeypatch: pytest.MonkeyPatch) -> None:
    from compassio_ml.challenges.c05 import train as train_module

    seen: list[set[str]] = []
    original = train_module.fit_pipeline  # type: ignore[attr-defined]

    def spy(pipe: Any, texts: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(set(map(str, texts)))
        return original(pipe, texts, *args, **kwargs)

    monkeypatch.setattr(train_module, "fit_pipeline", spy)
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 12, "uniform")
    gate = quarantine_gate(poisoned, small_config())
    assert gate.quarantined_ids
    quarantined_texts = set(poisoned.texts[np.isin(poisoned.ids, gate.quarantined_ids)].tolist())
    fit_downstream(gate.accepted, small_config().downstream, SPECS)
    assert seen and all(not (fitted & quarantined_texts) for fitted in seen)


def test_training_refuses_ungated_batches() -> None:
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 13, "uniform")
    with pytest.raises(GateBypassError):
        fit_downstream(poisoned, small_config().downstream, SPECS)  # type: ignore[arg-type]
    with pytest.raises(GateBypassError):
        AcceptedBatch(poisoned, "example", object())
    baseline = fit_downstream(
        Baseline("naive_poisoned", poisoned), small_config().downstream, SPECS
    )
    assert baseline.training_records == len(poisoned)


def test_gate_keeps_original_labels_and_reports_counts() -> None:
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 14, "uniform")
    gate = quarantine_gate(poisoned, small_config())
    by_id = dict(zip(poisoned.ids.tolist(), poisoned.labels.tolist(), strict=True))
    for record in gate.report["flagged_records"]:
        assert record["supplied_label"] == by_id[record["record_id"]]
    counts = gate.report["counts"]
    assert counts["accepted"]["records"] + counts["quarantined"]["records"] == len(poisoned)
    assert gate.report["input_fingerprint"] == poisoned.fingerprint()
    assert len(gate.accepted.batch) == len(gate.accepted_ids)
    assert gate.report["detector_version"] == "compassio-c05-detector-1.0.0"


def test_challenge_code_never_touches_sealed_evaluations_or_the_backend() -> None:
    for path in PACKAGE.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in (
            "compassio_api",
            "final_evaluation",
            "test_access",
            "trusted_model_releases",
            "compassio_dev.sqlite",
            "models_v2_dev",
        ):
            assert forbidden not in text, (path.name, forbidden)


def test_cohort_rights_check_refuses_restricted_sources(tmp_path: Path) -> None:
    from compassio_ml.external.paths import V2Paths
    from compassio_ml.model_v2.data import DataIntegrityError, check_rights

    paths = V2Paths(REPO, tmp_path / "out", None, None)
    check_rights(paths, {"iati_fcdo", "iati_ec_intpa"})  # the C05 batch sources: permitted
    with pytest.raises(DataIntegrityError):
        check_rights(paths, {"gcf_project_pages"})  # robots ai-train=no: never trained on


def test_peak_memory_is_measured() -> None:
    from compassio_ml.challenges.c05.experiment import peak_memory_mb

    value = peak_memory_mb()
    assert value is not None and value > 0


# ----------------------------------------------------------------------------- policies (addendum)
def _example_detector(n: int = 6) -> Any:
    from compassio_ml.challenges.c05.detector import DetectorResult

    def arr(values: list[Any]) -> np.ndarray:
        return np.array(values)

    # records: 0 both signals; 1 model only; 2 model only; 3 both (label 1, non-energy, weak);
    # 4 both (label 1, non-energy, strong); 5 nothing
    return DetectorResult(
        p_positive=arr([0.9, 0.8, 0.85, 0.3, 0.02, 0.5]),
        p_other=arr([0.9, 0.8, 0.85, 0.7, 0.98, 0.5]),
        threshold_other=arr([0.6] * n),
        model_flag=arr([True, True, True, True, True, False]),
        knn_agreement=arr([0.1, 0.5, 0.5, 0.2, 0.0, 0.6]),
        knn_similarity=arr([0.3] * n),
        knn_evidence=arr([True] * n),
        knn_flag=arr([True, False, False, True, True, False]),
        suspicion=arr([0.9, 0.6, 0.65, 0.75, 0.99, 0.4]),
        status=arr(
            [
                "quarantined",
                "insufficient_evidence",
                "insufficient_evidence",
                "quarantined",
                "quarantined",
                "accepted",
            ]
        ),
        fold=arr([0] * n),
        reasons=tuple(f"example reason {i}" for i in range(n)),
        thresholds={},
    )


def _example_policy_batch() -> SuppliedBatch:
    return SuppliedBatch.create(
        np.array([f"example:{i}" for i in range(6)]),
        np.array([f"example_text_{i}" for i in range(6)]),
        np.array([0, 0, 0, 1, 1, 0]),
        np.array([f"example_g{i}" for i in range(6)]),
        np.array(["example_pub"] * 6),
    )


HARD = {
    "provenance_second_signal": True,
    "protect_provenance_corroborated_positives": True,
    "positive_non_energy_strict": {"max_knn_agreement": 0.0667, "min_probability_margin": 0.1},
}


def test_two_signal_policy_equals_the_deployed_detector_status() -> None:
    from compassio_ml.challenges.c05.policy import two_signal

    det = _example_detector()
    assert np.array_equal(two_signal(det).status, det.status)


def test_hardened_policy_uses_provenance_and_protects_ambiguous_positives() -> None:
    from compassio_ml.challenges.c05.policy import Metadata, hardened

    meta = Metadata(
        sector_codes=np.array(["41030", "11110", "41010;15110", "12220", "12220", "41030"]),
        non_energy=np.array([True] * 6),
    )
    decision = hardened(
        _example_policy_batch(), _example_detector(), meta, frozenset({"41030", "41010"}), HARD
    )
    status = decision.status.tolist()
    assert status[0] == "quarantined"  # both signals
    assert status[1] == "insufficient_evidence"  # model only, no provenance code
    assert status[2] == "quarantined"  # model + provenance-inconsistent (label 0, code 41010)
    assert status[3] == "insufficient_evidence"  # label-1 non-energy, weak evidence -> review
    assert status[4] == "quarantined"  # label-1 non-energy with strong evidence
    assert status[5] == "insufficient_evidence"  # provenance alone never quarantines
    assert "provenance-inconsistent" in decision.reasons[2]
    assert decision.provenance_inconsistent.tolist() == [True, False, True, False, False, True]


def test_corroborated_positive_is_never_quarantined() -> None:
    from compassio_ml.challenges.c05.policy import Metadata, hardened

    meta = Metadata(sector_codes=np.array(["41030"] * 6), non_energy=np.array([False] * 6))
    decision = hardened(
        _example_policy_batch(), _example_detector(), meta, frozenset({"41030"}), HARD
    )
    assert decision.status[4] == "insufficient_evidence"  # label 1 + intrinsic code: protected
    assert "corroborates label 1" in decision.reasons[4]


def test_top_share_policy_quarantines_exactly_that_share() -> None:
    from compassio_ml.challenges.c05.policy import top_share

    decision = top_share(_example_detector(), 0.5)
    assert (decision.status == "quarantined").sum() == 3
    assert set(np.flatnonzero(decision.status == "quarantined").tolist()) == {0, 3, 4}


def test_gate_reports_the_policy_only_when_not_deployed_default() -> None:
    poisoned, _ = inject_label_flips(example_batch(), 0.05, 21, "uniform")
    cfg = small_config()
    default = quarantine_gate(poisoned, cfg)
    assert "policy" not in default.report

    def everything_to_review(det: Any) -> tuple[str, np.ndarray, tuple[str, ...]]:
        return "example_policy", np.full(len(det.status), "insufficient_evidence"), det.reasons

    custom = quarantine_gate(poisoned, cfg, policy=everything_to_review)
    assert custom.report["policy"] == "example_policy"
    assert not custom.quarantined_ids and len(custom.accepted_ids) == len(poisoned)


def test_policy_module_never_imports_the_attack() -> None:
    tree = ast.parse((PACKAGE / "policy.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "compassio_ml.challenges.c05.attack" not in imported
