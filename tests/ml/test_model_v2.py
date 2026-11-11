"""ML v2 fast track: leakage, rights, CV, thresholds, selection, fingerprint, artifact guards.

All data here is ARTIFICIAL (``example_*`` tokens, invented groups). It exercises logic only and
is never reported as model evidence.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from compassio_ml.external.paths import V2Paths
from compassio_ml.model_v2 import candidates as cm
from compassio_ml.model_v2 import evaluate as ev
from compassio_ml.model_v2.artifact import (
    CandidateArtifactError,
    ExperimentalClassifier,
    save_candidate,
)
from compassio_ml.model_v2.benchmark import FoldFeatures, run_population, select_champion
from compassio_ml.model_v2.data import (
    DataIntegrityError,
    check_isolation,
    check_rights,
    membership_sha256,
    prepare,
)
from compassio_ml.model_v2.plan import PlanError, load_plan, plan_sha256
from compassio_ml.modeling.metrics import GroupBootstrap, best_f1_threshold

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / "configs" / "ml_v2_fast_experiment.yaml"


def small_plan() -> Any:
    """The real plan with tiny feature limits and a one-config grid (logic tests only)."""
    plan = load_plan(PLAN)
    features = {
        "word": {**plan.features["word"], "min_df": 1, "max_df": 1.0},
        "char": {**plan.features["char"], "min_df": 1, "max_df": 1.0, "max_features": 2000},
    }
    cands = tuple(
        c if c.grid == "best_of_ABC" else c.model_copy(update={"grid": c.grid[:1]})
        for c in plan.candidates
    )
    return plan.model_copy(update={"features": features, "candidates": cands})


def example_frame(n_groups: int = 60, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        positive = g % 3 == 0
        source = "iati_fcdo" if g % 2 else "iati_ec_intpa"
        for k in range(2):
            words = ["example_project", f"example_item_{g}_{k}"]
            words += ["example_solar", "example_resilience"] if positive else ["example_school"]
            if rng.random() < 0.2:
                words.append("example_noise")
            rows.append(
                {
                    "candidate_id": f"example:{g}:{k}",
                    "source_id": source,
                    "part": "train",
                    "text": " ".join(words),
                    "title": " ".join(words),
                    "description": "",
                    "y": int(positive),
                    "mitigation": float(positive),
                    "adaptation": float(positive and g % 2),
                    "non_energy": bool(g % 4),
                    "sector_family": "example_sector",
                    "group": f"g{g}",
                    "family": f"f{g}",
                    "text_sha256": f"h{g}{k}",
                    "v1_consumed_test": False,
                }
            )
    frame = pd.DataFrame(rows)
    frame["adaptation_only"] = (frame["adaptation"] > 0) & (frame["mitigation"] == 0)
    frame["mitigation_only"] = (frame["mitigation"] > 0) & (frame["adaptation"] == 0)
    return frame


# ------------------------------------------------------------------------------------ plan
def test_plan_loads_and_hash_is_enforced() -> None:
    plan = load_plan(PLAN, plan_sha256(PLAN))

    assert plan.selection.primary_metric == "non_energy_average_precision"
    assert plan.inputs.memberships["train"].records == 13317
    with pytest.raises(PlanError):
        load_plan(PLAN, "0" * 64)


# ------------------------------------------------------------------------------- data rules
def test_prepare_derives_label_and_slices_from_donor_markers() -> None:
    source = pd.DataFrame(
        {
            "candidate_id": ["example:1", "example:2", "example:3"],
            "source_id": ["iati_fcdo"] * 3,
            "title_clean": ["example a", "example b", "example c"],
            "description_clean": ["d", "d", "d"],
            "donor_rio_overall": [0.0, 1.0, 2.0],
            "donor_rio_mitigation": [0.0, 0.0, 2.0],
            "donor_rio_adaptation": [0.0, 1.0, 0.0],
            "is_energy_sector": [False, False, True],
            "sector_family": ["example", None, "energy"],
            "partition_group_id": ["g1", "g2", "g3"],
            "project_family_id": ["f1", "f2", "f3"],
            "text_sha256": ["a", "b", "c"],
            "v1_consumed_test": [False, False, False],
        }
    )
    out = prepare(source, "train")

    assert out["y"].tolist() == [0, 1, 1]
    assert out["adaptation_only"].tolist() == [False, True, False]
    assert out["non_energy"].tolist() == [True, True, False]
    assert out["sector_family"].tolist()[1] == "unknown"
    assert set(out.columns) >= {"text", "title", "description"}


@pytest.mark.parametrize("column", ["group", "family", "text_sha256"])
def test_isolation_refuses_anything_spanning_train_and_valid(column: str) -> None:
    frame = example_frame(4)
    frame["part"] = np.where(frame.index == 0, "valid", "train")
    frame[column] = frame[column].where(frame.index != 0, frame[column].iloc[2])

    with pytest.raises(DataIntegrityError):
        check_isolation(frame)


def test_isolation_refuses_consumed_v1_tests() -> None:
    frame = example_frame(4)
    frame.loc[0, "v1_consumed_test"] = True

    with pytest.raises(DataIntegrityError):
        check_isolation(frame)


def test_rights_refuse_restricted_and_unknown_sources() -> None:
    paths = V2Paths(
        repo_root=REPO,
        output_root=REPO / "data" / "ml_v2",
        input_data_root=None,
        v1_project_root=None,
    )
    check_rights(paths, {"iati_fcdo", "iati_ec_intpa", "aiddata"})
    for source in ("gcf_project_pages", "worldbank_projects", "example_unknown"):
        with pytest.raises((DataIntegrityError, KeyError)):
            check_rights(paths, {source})


def test_membership_hash_depends_on_ids_and_labels() -> None:
    frame = example_frame(4)
    flipped = frame.assign(y=1 - frame["y"])

    assert membership_sha256(frame) == membership_sha256(frame.sample(frac=1, random_state=1))
    assert membership_sha256(frame) != membership_sha256(flipped)


# ----------------------------------------------------------------------------- CV/features
def test_group_folds_never_split_a_group() -> None:
    frame = example_frame(30)
    for tr, te in cm.group_folds(frame["y"].to_numpy(), frame["group"].to_numpy(), 3, 7):
        assert not set(frame["group"].iloc[tr]) & set(frame["group"].iloc[te])


def test_fold_vectorisers_are_fitted_on_training_rows_only() -> None:
    plan = small_plan()
    frame = example_frame(30)
    cache = FoldFeatures(
        frame["text"].to_numpy(), frame["y"].to_numpy(), frame["group"].to_numpy(), plan, {"word"}
    )
    texts = frame["text"].to_numpy()
    for i, (tr, te) in enumerate(cache.folds):
        Xtr, Xte = cache.get("word", i)
        test_only = {f"example_item_{g.removeprefix('g')}_0" for g in frame["group"].iloc[te]}
        vec = cm.vectorizer(plan.features["word"]).fit(texts[tr])
        assert not test_only & set(vec.vocabulary_)
        assert Xtr.shape[1] == Xte.shape[1] == len(vec.vocabulary_)


def test_sample_weights_are_training_only_and_normalised() -> None:
    frame = example_frame(10)
    frame.loc[frame.index[:4], "source_id"] = "iati_fcdo"
    pub = cm.sample_weights(frame, "publisher_balanced")
    fam = cm.sample_weights(frame, "family_inverse")

    assert pub is not None and fam is not None
    assert pytest.approx(pub.mean()) == 1.0 and pytest.approx(fam.mean()) == 1.0
    totals = pd.Series(pub).groupby(frame["source_id"].to_numpy()).sum()
    assert pytest.approx(totals.iloc[0]) == totals.iloc[1]
    assert cm.sample_weights(frame, "none") is None


def test_platt_svm_needs_groups_and_returns_probabilities() -> None:
    plan = small_plan()
    frame = example_frame(30)
    X = cm.vectorizer(plan.features["word"]).fit_transform(frame["text"])
    clf = cm.PlattLinearSVC(C=0.5, n_splits=3, random_state=1)
    with pytest.raises(ValueError):
        clf.fit(X, frame["y"].to_numpy())
    clf.fit(X, frame["y"].to_numpy(), groups=frame["group"].to_numpy())
    proba = clf.predict_proba(X)[:, 1]

    assert ((proba >= 0) & (proba <= 1)).all()


# --------------------------------------------------------------------------------- runner
def test_population_threshold_comes_from_train_oof_and_trials_are_logged() -> None:
    plan = small_plan()
    frame = example_frame(60)
    result = run_population(
        "example", frame, plan, ["A_word_lr", "E_family_inverse"], log=lambda _: None
    )

    names = [f.name for f in result.finalists]
    assert names == ["A_word_lr", "E_family_inverse"]
    assert all(t["status"] == "ok" for t in result.trials)
    assert result.finalists[1].weighting == "family_inverse"
    a = result.finalists[0]
    assert np.isfinite(a.threshold) and a.train_records == len(frame)


def _row(key: str, ne_ap: float, ne_p: float, ao: float, ap: float, size: int) -> dict[str, Any]:
    return {
        "key": key,
        "artifact_bytes": size,
        "summary": {
            "non_energy_average_precision": ne_ap,
            "non_energy_precision": ne_p,
            "adaptation_only_recall": ao,
            "average_precision": ap,
        },
    }


def test_selection_rule_guard_primary_and_tie_breakers() -> None:
    plan = load_plan(PLAN)
    rows = [
        _row("a", 0.90, 0.50, 0.9, 0.9, 1),  # fails the precision guard
        _row("b", 0.80, 0.70, 0.40, 0.80, 10),
        _row("c", 0.798, 0.70, 0.60, 0.70, 10),  # tied within window, better adaptation recall
        _row("d", 0.70, 0.90, 0.99, 0.99, 1),
    ]
    assert select_champion(rows, plan)["champion"] == "c"
    assert select_champion([rows[0]], plan)["decision"] == "retain_v1"


# ------------------------------------------------------------------------------- metrics
def test_slices_are_suppressed_below_the_minimum() -> None:
    frame = example_frame(10)
    out = ev.slice_table(
        frame,
        frame["y"].to_numpy().astype(float),
        0.5,
        True,
        ("example_sector",),
        min_records=30,
        min_positives=15,
    )

    assert out["sector:example_sector"]["suppressed"] is True
    assert out["positives:adaptation_only"]["positives"] == int(frame["adaptation_only"].sum())


def test_metrics_and_paired_difference_on_known_scores() -> None:
    frame = example_frame(30)
    y = frame["y"].to_numpy()
    perfect = y.astype(float)
    metrics = ev.basic(y, perfect, 0.5, True)
    boot = GroupBootstrap.build(frame["group"].to_numpy(), 50, 1)
    same = ev.paired_difference(frame, perfect, perfect, boot, 0.95)

    assert metrics["f1"] == 1.0 and metrics["average_precision"] == 1.0
    assert same["difference"] == 0.0 and same["low"] == 0.0 == same["high"]
    assert best_f1_threshold(y, perfect) == 1.0


# --------------------------------------------------------------------------- fingerprint
def _fit(C: float) -> Pipeline:
    plan = small_plan()
    frame = example_frame(30)
    pipe = cm.make_pipeline(
        "word", "lr", {"C": C, "class_weight": "balanced"}, plan.features, plan.seed, 3
    )
    return cm.fit_pipeline(
        pipe, frame["text"].to_numpy(), frame["y"].to_numpy(), frame["group"].to_numpy(), None, "lr"
    )


def test_fingerprint_is_stable_and_content_sensitive() -> None:
    a, b, c = _fit(1.0), _fit(1.0), _fit(2.0)

    assert cm.fingerprint(a) == cm.fingerprint(b)
    assert cm.fingerprint(a) != cm.fingerprint(c)


# ------------------------------------------------------------------------------ artifact
def _save(tmp_path: Path) -> Path:
    directory = tmp_path / "example_candidate"
    save_candidate(
        _fit(1.0), directory, {"candidate_id": "example", "classifier": "lr", "threshold": 0.5}
    )
    return directory


def test_candidate_round_trip_and_overwrite_refusal(tmp_path: Path) -> None:
    directory = _save(tmp_path)
    model = ExperimentalClassifier.load(directory, tmp_path / "no_registry.json")

    prediction = model.predict("example_solar example_resilience", "")
    assert prediction.status == "development_candidate"
    assert "EXPERIMENTAL" in prediction.limitation
    with pytest.raises(FileExistsError):
        _save(tmp_path)
    with pytest.raises(ValueError):
        model.predict(" ", None)


def test_corrupt_or_mismatched_candidates_are_refused(tmp_path: Path) -> None:
    directory = _save(tmp_path)
    manifest_path = directory / "candidate_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))

    registry = tmp_path / "trusted.json"
    registry.write_text(json.dumps({"example_release": manifest["artifact_sha256"]}))
    with pytest.raises(CandidateArtifactError, match="trusted release"):
        ExperimentalClassifier.load(directory, registry)

    manifest_path.write_text(json.dumps({**manifest, "model_fingerprint": "0" * 64}))
    with pytest.raises(CandidateArtifactError, match="fingerprint"):
        ExperimentalClassifier.load(directory, tmp_path / "none.json")

    manifest_path.write_text(json.dumps({**manifest, "status": "release"}))
    with pytest.raises(CandidateArtifactError, match="development-candidate"):
        ExperimentalClassifier.load(directory, tmp_path / "none.json")

    manifest_path.write_text(json.dumps(manifest))
    (directory / "model.joblib").write_bytes(b"example corrupted bytes")
    with pytest.raises(CandidateArtifactError, match="checksum"):
        ExperimentalClassifier.load(directory, tmp_path / "none.json")


# ------------------------------------------------------------------- no sealed-data access
def test_fast_track_code_never_references_sealed_or_test_pools() -> None:
    package = REPO / "packages" / "compassio_ml" / "src" / "compassio_ml" / "model_v2"
    text = "\n".join(p.read_text("utf-8") for p in package.glob("*.py"))

    for forbidden in (
        "sealed_external_test",
        "EXTERNAL",
        "allow_test=True",
        "load_partitions",
        "final_evaluate",
        "raw_db",
    ):
        assert forbidden not in text, forbidden


# ---------------------------------------------------------------------------- escalation
def test_escalation_addendum_hash_and_encoder_guards(tmp_path: Path) -> None:
    import pickle

    from compassio_ml.model_v2.escalation import FrozenSentenceEncoder, load_addendum

    addendum_path = REPO / "configs" / "ml_v2_fast_escalation.yaml"
    addendum = load_addendum(addendum_path, plan_sha256(addendum_path))
    assert addendum.base_plan_sha256 == plan_sha256(PLAN)
    assert addendum.replacement_rule.otherwise == "keep_base_champion"
    with pytest.raises(ValueError):
        load_addendum(addendum_path, "0" * 64)

    (tmp_path / "model.safetensors").write_bytes(b"example not the pinned weights")
    encoder = FrozenSentenceEncoder(str(tmp_path), weights_sha256="0" * 64)
    with pytest.raises(ValueError, match="pinned sha256"):  # checked before any model import
        encoder.transform(["example text"])
    encoder.__dict__["_loaded"] = object()
    restored = pickle.loads(pickle.dumps(encoder))
    assert "_loaded" not in restored.__dict__  # the heavy model is never pickled
    assert encoder.fit(["example"]).is_fitted_ is True  # fit learns nothing
