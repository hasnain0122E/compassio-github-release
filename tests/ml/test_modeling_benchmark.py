"""End-to-end benchmark, data loading and inference on an ARTIFICIAL dataset.

The synthetic "projects" below are invented text that exercises code paths. Their scores are
meaningless and must never be reported as model performance.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

import compassio_ml.modeling.benchmark as benchmark_module
from compassio_ml.modeling.benchmark import Benchmark, group_folds
from compassio_ml.modeling.config import BenchmarkConfig
from compassio_ml.modeling.data import FinalTestAccessError, load_partitions
from compassio_ml.modeling.estimators import make_estimator
from compassio_ml.modeling.frozen import FrozenDataError, FrozenPaths, write_lock
from compassio_ml.modeling.inference import (
    ArtifactIntegrityError,
    ClimateRelevanceClassifier,
    EmptyInputError,
)
from compassio_ml.modeling.tracking import RunExistsError, read_trials

CLIMATE = [
    "solar power plant",
    "wind farm",
    "hydropower station",
    "flood control embankment",
    "drought resilience programme",
    "renewable energy grid",
]
OTHER = [
    "school building",
    "hospital equipment",
    "road paving",
    "scholarship programme",
    "stadium construction",
    "government office",
]


def synthetic_repo(root: Path, n_groups: int = 120) -> Path:
    rng = np.random.default_rng(3)
    rows, membership = [], []
    rid = 0
    for g in range(n_groups):
        positive = g % 3 == 0
        split = ["train"] * 6 + ["validation"] * 2 + ["test"] * 2
        part = split[g % 10]
        for _ in range(int(rng.integers(1, 4))):
            rid += 1
            words = rng.choice(CLIMATE if positive else OTHER, size=2)
            pk = g % 7 == 0
            rows.append(
                {
                    "record_id": str(rid),
                    "is_climate_related": positive,
                    "rio_overall": 2 if positive else 0,  # must never reach the features
                    "title_clean": f"Example {words[0]} {g}",
                    "description_clean": f"Example project financing a {words[0]} and {words[1]}.",
                    "commitment_year": 2000 + g % 22,
                    "recipient_iso3": "PAK" if pk else "EXL",
                    "recipient": "Pakistan" if pk else "Exampleland",
                    "sector_name": "ENERGY" if positive and g % 2 else "OTHER",
                    "is_pakistan": pk,
                    "retrospective_text_warning": g % 3 == 0,
                    "amount_original": None if g % 4 == 0 else 100.0,
                    "eligibility_status": "eligible",
                    "leakage_group_id": f"g{g:03d}",
                }
            )
            membership.append(
                {
                    "record_id": str(rid),
                    "leakage_group_id": f"g{g:03d}",
                    "eligibility_status": "eligible",
                    "split_primary": part,
                    "split_chronological": part,
                    "split_pakistan_holdout": "test"
                    if pk
                    else ("validation" if part == "test" else part),
                }
            )
    data = root / "data" / "processed"
    data.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(data / "research_projects.parquet", index=False)
    pd.DataFrame(membership).to_parquet(data / "research_split_membership_v1.parquet", index=False)
    configs = root / "configs"
    configs.mkdir()
    (configs / "research_split_v1.yaml").write_text("version: example\n", encoding="utf-8")
    write_lock(paths_of(root))
    return root


def paths_of(root: Path) -> FrozenPaths:
    return FrozenPaths(
        root / "data/processed/research_projects.parquet",
        root / "data/processed/research_split_membership_v1.parquet",
        root / "configs/research_split_v1.yaml",
        root / "configs/research_split_v1.lock.json",
    )


def tiny_config() -> BenchmarkConfig:
    return BenchmarkConfig.model_validate(
        {
            "version": "example_benchmark",
            "seed": 11,
            "target": "is_climate_related",
            "data": {
                "table": "data/processed/research_projects.parquet",
                "membership": "data/processed/research_split_membership_v1.parquet",
                "split_config": "configs/research_split_v1.yaml",
                "split_lock": "configs/research_split_v1.lock.json",
            },
            "tfidf_presets": {"p": {"ngram_range": [1, 1], "min_df": 1, "max_df": 1.0}},
            "inner_cv": {"n_splits": 2, "shuffle": True},
            "threshold_objective": "f1",
            "bootstrap": {"resamples": 100, "confidence": 0.95},
            "selection": {
                "primary_metric": "average_precision",
                "tie_rule": "paired_bootstrap_ci_includes_zero",
                "tie_breakers": ["provides_probability"],
            },
            "slice_min_records": 5,
            "slice_min_positives": 2,
            "suites": {
                "tiny": {
                    "representations": ["title_description"],
                    "tfidf": ["p"],
                    "calibrate_best_svm": True,
                    "candidates": {
                        "majority": [{}],
                        "keyword": [{}],
                        "multinomial_nb": [{"alpha": 1.0}],
                        "logistic_regression": [
                            {"C": 1.0, "class_weight": "balanced"},
                            {"C": 4.0, "class_weight": None},
                        ],
                        "linear_svm": [{"C": 1.0, "class_weight": "balanced"}],
                    },
                }
            },
        }
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return synthetic_repo(tmp_path / "repo")


def run(repo: Path, out: Path, **kw: object) -> benchmark_module.BenchmarkResult:
    return Benchmark(tiny_config(), "primary", "tiny", repo, out, **kw).run()  # type: ignore[arg-type]


# ---------------------------------------------------------------- data loading
def test_partitions_use_only_allowlisted_features(repo: Path) -> None:
    p = paths_of(repo)
    parts = load_partitions(p.table, p.membership, "primary")

    assert set(parts) == {"train", "validation"}
    for part in parts.values():
        assert list(part.features.columns) == ["title_clean", "description_clean"]
        assert (
            "rio_overall" not in part.meta.columns and "is_climate_related" not in part.meta.columns
        )
    assert set(parts["train"].groups).isdisjoint(parts["validation"].groups)


def test_test_partition_cannot_be_loaded(repo: Path) -> None:
    p = paths_of(repo)
    with pytest.raises(FinalTestAccessError):
        load_partitions(p.table, p.membership, "primary", ("train", "test"))
    with pytest.raises(ValueError, match="protocol"):
        load_partitions(p.table, p.membership, "random_split")


def test_pakistan_protocol_training_excludes_pakistan(repo: Path) -> None:
    p = paths_of(repo)
    parts = load_partitions(p.table, p.membership, "pakistan_holdout")

    assert not parts["train"].meta["is_pakistan"].any()
    assert not parts["validation"].meta["is_pakistan"].any()


def test_group_folds_never_split_a_group() -> None:
    y = np.array([0, 1] * 30)
    groups = np.repeat(np.arange(20), 3)
    for train_idx, test_idx in group_folds(y, groups, 3, seed=5):
        assert set(groups[train_idx]).isdisjoint(groups[test_idx])


# ---------------------------------------------------------------- end-to-end benchmark
def test_benchmark_runs_validation_only_and_records_everything(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []
    original = load_partitions

    def spy(*args: Any, **kwargs: Any) -> Any:
        calls.append(tuple(args[3]) if len(args) > 3 else ("train", "validation"))
        assert not kwargs.get("allow_test")
        return original(*args, **kwargs)

    monkeypatch.setattr(benchmark_module, "load_partitions", spy)
    result = run(repo, tmp_path / "out")

    assert calls == [("train", "validation")]
    manifest = json.loads((result.run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["test_partition_loaded"] is False
    trials = read_trials(result.run_dir / "trials.jsonl")
    completed = [t for t in trials if t["status"] == "completed"]
    assert {t["stage"] for t in completed} == {"inner_cv", "finalist"}
    assert len([t for t in trials if t["stage"] == "inner_cv" and t["status"] == "completed"]) == 4
    keys = {f.key for f in result.finalists}
    assert "linear_svm_calibrated|title_description|p" in keys
    predictions = pd.read_parquet(result.run_dir / "winner_validation_predictions.parquet")
    assert set(predictions["record_id"]) == set(result.validation.record_ids)
    assert sum(r["is_provisional_winner"] for r in result.ranking) == 1
    for name in (
        "finalists.csv",
        "validation_slices.csv",
        "reliability.csv",
        "metrics_deterministic.json",
        "model/model.joblib",
        "model/model_metadata.json",
    ):
        assert (result.run_dir / name).is_file(), name


def test_benchmark_is_reproducible(repo: Path, tmp_path: Path) -> None:
    a = run(repo, tmp_path / "a")
    b = run(repo, tmp_path / "b")

    for name in (
        "metrics_deterministic.json",
        "validation_slices.csv",
        "winner_validation_predictions.parquet",
        "model/model.joblib",
    ):
        assert (a.run_dir / name).read_bytes() == (b.run_dir / name).read_bytes(), name


def test_existing_run_is_not_overwritten(repo: Path, tmp_path: Path) -> None:
    run(repo, tmp_path / "out")
    with pytest.raises(RunExistsError):
        run(repo, tmp_path / "out")
    run(repo, tmp_path / "out", overwrite=True)


def test_failed_trial_is_recorded(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = make_estimator

    def failing(algorithm: str, *args: Any, **kwargs: Any) -> Any:
        if algorithm == "multinomial_nb":
            raise RuntimeError("example injected failure")
        return original(algorithm, *args, **kwargs)

    monkeypatch.setattr(benchmark_module, "make_estimator", failing)
    result = run(repo, tmp_path / "out")

    failed = [t for t in read_trials(result.run_dir / "trials.jsonl") if t["status"] == "failed"]
    assert failed and all(t["algorithm"] == "multinomial_nb" for t in failed)
    assert "example injected failure" in str(failed[0]["error"])
    assert not any(f.algorithm == "multinomial_nb" for f in result.finalists)


def test_changed_split_refuses_to_run(repo: Path, tmp_path: Path) -> None:
    p = paths_of(repo)
    m = pd.read_parquet(p.membership)
    m.loc[m.index[0], "split_primary"] = (
        "validation" if m.loc[m.index[0], "split_primary"] == "train" else "train"
    )
    m.to_parquet(p.membership, index=False)

    with pytest.raises(FrozenDataError):
        run(repo, tmp_path / "out")


# ---------------------------------------------------------------- inference
def test_inference_wrapper(repo: Path, tmp_path: Path) -> None:
    result = run(repo, tmp_path / "out")
    model = ClimateRelevanceClassifier.load(result.run_dir / "model")

    prediction = model.predict(
        "Example solar power plant", "Example project financing a wind farm."
    )

    assert isinstance(prediction.is_climate_related, bool)
    assert prediction.score_kind in {"probability", "decision_score"}
    assert (prediction.probability is None) == (prediction.score_kind != "probability")
    assert prediction.model_version.startswith("primary__tiny__")
    assert set(prediction.dataset_version) == {
        "table_sha256",
        "membership_sha256",
        "split_config_sha256",
    }
    with pytest.raises(EmptyInputError):
        model.predict("  ", None)


def test_tampered_artifact_is_refused(repo: Path, tmp_path: Path) -> None:
    result = run(repo, tmp_path / "out")
    artifact = result.run_dir / "model" / "model.joblib"
    artifact.write_bytes(artifact.read_bytes() + b"tamper")

    with pytest.raises(ArtifactIntegrityError):
        ClimateRelevanceClassifier.load(result.run_dir / "model")
