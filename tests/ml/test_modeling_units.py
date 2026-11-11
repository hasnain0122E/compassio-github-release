"""Unit tests for Task 004 modeling components. ARTIFICIAL inputs only; never real metrics."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from compassio_ml.modeling.config import BenchmarkConfig, Suite, TfidfPreset, load_benchmark_config
from compassio_ml.modeling.estimators import (
    make_calibrated_svm,
    make_estimator,
    score_kind,
    scores,
)
from compassio_ml.modeling.features import (
    SEPARATOR,
    KeywordClassifier,
    build_text,
    build_texts,
    keyword_hits,
)
from compassio_ml.modeling.frozen import (
    FrozenDataError,
    FrozenPaths,
    require_frozen,
    verify_frozen,
    write_lock,
)
from compassio_ml.modeling.metrics import (
    GroupBootstrap,
    ap_statistic,
    best_f1_threshold,
    calibration_metrics,
    confusion,
    expected_calibration_error,
    predict_at,
    ranking_metrics,
    threshold_metrics,
)

REPO = Path(__file__).resolve().parents[2]
PRESET = TfidfPreset(ngram_range=(1, 1), min_df=1, max_df=1.0, max_features=None)


# ---------------------------------------------------------------- text construction
def test_build_text_representations() -> None:
    assert build_text("Example title", "Example description", "title") == "Example title"
    assert (
        build_text("Example title", "Example description", "description") == "Example description"
    )
    assert build_text("T", "D", "title_description") == f"T{SEPARATOR}D"
    assert build_text(None, "D", "title_description") == "D"
    assert build_text("T", pd.NA, "title_description") == "T"
    with pytest.raises(ValueError):
        build_text("T", "D", "summary")  # type: ignore[arg-type]


def test_build_texts_is_deterministic_and_validates() -> None:
    frame = pd.DataFrame({"title_clean": ["a", "b"], "description_clean": ["x", None]})
    first = build_texts(frame, "title_description")

    assert list(first) == [f"a{SEPARATOR}x", "b"]
    assert list(build_texts(frame, "title_description")) == list(first)
    with pytest.raises(ValueError):
        build_texts(frame, "everything")  # type: ignore[arg-type]


def test_keyword_baseline_is_fixed_and_learns_nothing() -> None:
    texts = ["Example solar power plant", "Example school building", "Flood control works"]
    model = KeywordClassifier().fit(texts, [0, 0, 0])  # labels cannot change the rule
    flipped = KeywordClassifier().fit(texts, [1, 1, 1])

    assert list(model.predict(texts)) == [1, 0, 1] == list(flipped.predict(texts))
    assert keyword_hits("Climate resilience and drought early warning") == 4
    assert keyword_hits("Example hospital") == 0


# ---------------------------------------------------------------- metrics
def test_confusion_and_threshold_metrics() -> None:
    y = np.array([1, 1, 0, 0, 1, 0])
    pred = np.array([1, 0, 0, 1, 1, 0])

    c = confusion(y, pred)
    m = threshold_metrics(y, pred)

    assert (c.tp, c.fn, c.fp, c.tn) == (2, 1, 1, 2)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["accuracy"] == pytest.approx(4 / 6)


def test_ranking_metrics_and_single_class() -> None:
    y = np.array([0, 0, 1, 1])
    perfect = ranking_metrics(y, np.array([0.1, 0.2, 0.8, 0.9]))

    assert perfect == {"average_precision": 1.0, "roc_auc": 1.0}
    assert ranking_metrics(np.array([0, 0]), np.array([0.1, 0.2])) == {
        "average_precision": None,
        "roc_auc": None,
    }


def test_best_f1_threshold_and_predict_at() -> None:
    y = np.array([0, 0, 1, 1, 0, 1])
    s = np.array([0.1, 0.4, 0.35, 0.8, 0.2, 0.9])

    t = best_f1_threshold(y, s)

    assert t == pytest.approx(0.35)
    assert list(predict_at(s, t)) == [0, 1, 1, 1, 0, 1]
    assert best_f1_threshold(np.array([0, 0]), np.array([0.1, 0.2])) == float("inf")


def test_calibration_metrics() -> None:
    y = np.array([0, 1] * 50)
    prob = np.full(100, 0.5)

    m = calibration_metrics(y, prob)

    assert m["brier"] == pytest.approx(0.25)
    assert expected_calibration_error(y, prob) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="probabilities"):
        calibration_metrics(y, np.full(100, 1.5))


def test_group_bootstrap_resamples_whole_groups() -> None:
    groups = np.array(["a", "a", "b", "b", "b", "c"])
    boot = GroupBootstrap.build(groups, resamples=50, seed=7)

    for idx in boot.index_sets:
        chosen = groups[idx]
        for g in set(chosen):
            # every selected group appears with all of its members (multiplicity of full size)
            assert (chosen == g).sum() % (groups == g).sum() == 0
    again = GroupBootstrap.build(groups, resamples=50, seed=7)
    assert all((a == b).all() for a, b in zip(boot.index_sets, again.index_sets, strict=True))


def test_bootstrap_interval_contains_point_estimate() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 400)
    s = y + rng.normal(0, 0.8, 400)
    groups = np.arange(400) // 2
    boot = GroupBootstrap.build(groups, resamples=300, seed=1)

    lo, hi, n = boot.interval(ap_statistic(y, s), 0.95)
    point = ranking_metrics(y, s)["average_precision"]

    assert lo is not None and hi is not None and point is not None
    assert lo <= point <= hi
    assert n == 300


# ---------------------------------------------------------------- estimators and fitting
def test_tfidf_is_fitted_on_training_texts_only() -> None:
    train = np.array(["example solar plant", "example road", "example wind farm", "example school"])
    validation = np.array(["validationonlytoken climate"])
    model = make_estimator("logistic_regression", {"C": 1.0, "class_weight": None}, PRESET, 0)

    model.fit(train, [1, 0, 1, 0])
    vocabulary = model.named_steps["tfidf"].vocabulary_
    model.predict(validation)  # transform only; must not extend the vocabulary

    assert "validationonlytoken" not in vocabulary
    assert model.named_steps["tfidf"].vocabulary_ == vocabulary


@pytest.mark.parametrize(
    ("algorithm", "params"),
    [
        ("random_forest", {}),
        ("logistic_regression", {"C": 1.0, "penalty": "l1"}),
        ("multinomial_nb", {"alpha": 1.0, "fit_prior": False}),
    ],
)
def test_invalid_estimator_configuration_rejected(algorithm: str, params: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        make_estimator(algorithm, params, PRESET, 0)


def test_text_models_require_a_tfidf_preset() -> None:
    with pytest.raises(ValueError, match="TF-IDF"):
        make_estimator("linear_svm", {"C": 1.0}, None, 0)


def test_svm_scores_are_decision_scores_and_calibrated_are_probabilities() -> None:
    texts = np.array(["example solar plant", "example road works"] * 20, dtype=object)
    y = np.array([1, 0] * 20)
    halves = (np.arange(0, 20), np.arange(20, 40))  # both classes in each half
    folds = [(halves[0], halves[1]), (halves[1], halves[0])]
    svm = make_estimator("linear_svm", {"C": 1.0}, PRESET, 0).fit(texts, y)
    cal = make_calibrated_svm({"C": 1.0}, PRESET, 0, folds).fit(texts, y)

    margin = scores(svm, texts, "linear_svm")
    prob = scores(cal, texts, "linear_svm_calibrated")

    assert score_kind("linear_svm") == "decision_score"
    assert score_kind("linear_svm_calibrated") == "probability"
    assert (margin < 0).any()  # raw margins are not probabilities
    assert ((prob >= 0) & (prob <= 1)).all()


# ---------------------------------------------------------------- configuration
def test_repository_benchmark_config_loads() -> None:
    config = load_benchmark_config(REPO / "configs" / "ml_benchmark_v1.yaml")

    assert config.target == "is_climate_related"
    assert {"fast", "full"} <= set(config.suites)
    assert config.selection.primary_metric == "average_precision"


@pytest.mark.parametrize(
    "candidates",
    [
        {"logistic_regression": [{"C": 1.0, "class_weight": "auto"}]},
        {"logistic_regression": [{"C": -1.0}]},
        {"linear_svm": [{"C": 1.0, "kernel": "rbf"}]},
        {"multinomial_nb": []},
    ],
)
def test_invalid_suite_rejected(candidates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Suite(representations=("title",), tfidf=("p",), candidates=candidates)  # type: ignore[arg-type]


def test_suite_with_unknown_preset_rejected() -> None:
    data = load_benchmark_config(REPO / "configs" / "ml_benchmark_v1.yaml").model_dump(mode="json")
    data["suites"]["fast"]["tfidf"] = ["missing_preset"]

    with pytest.raises(ValidationError, match="unknown tfidf presets"):
        BenchmarkConfig.model_validate(data)


# ---------------------------------------------------------------- frozen lock
def _frozen(tmp_path: Path) -> FrozenPaths:
    membership = pd.DataFrame(
        {
            "record_id": ["1", "2", "3"],
            "leakage_group_id": ["g1", "g2", "g3"],
            "eligibility_status": ["eligible"] * 3,
            "split_primary": ["train", "validation", "test"],
            "split_chronological": ["train", "validation", "test"],
            "split_pakistan_holdout": ["train", "validation", "test"],
        }
    )
    paths = FrozenPaths(
        tmp_path / "t.parquet", tmp_path / "m.parquet", tmp_path / "c.yaml", tmp_path / "lock.json"
    )
    membership.to_parquet(paths.membership)
    pd.DataFrame({"record_id": ["1", "2", "3"]}).to_parquet(paths.table)
    paths.split_config.write_text("version: example\n", encoding="utf-8")
    return paths


def test_lock_detects_any_change(tmp_path: Path) -> None:
    paths = _frozen(tmp_path)
    write_lock(paths)
    assert verify_frozen(paths).ok

    paths.split_config.write_text("version: changed\n", encoding="utf-8")
    report = verify_frozen(paths)

    assert not report.ok and "split_config" in report.errors[0]
    with pytest.raises(FrozenDataError, match="refusing to run"):
        require_frozen(paths)


def test_lock_detects_changed_membership(tmp_path: Path) -> None:
    paths = _frozen(tmp_path)
    write_lock(paths)
    m = pd.read_parquet(paths.membership)
    m.loc[0, "split_primary"] = "validation"
    m.to_parquet(paths.membership)

    assert any("membership" in e for e in verify_frozen(paths).errors)


def test_missing_lock_raises(tmp_path: Path) -> None:
    with pytest.raises(FrozenDataError, match="not found"):
        verify_frozen(_frozen(tmp_path))
