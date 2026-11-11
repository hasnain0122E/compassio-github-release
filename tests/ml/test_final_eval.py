"""Task 005 one-shot final evaluation safeguards, on an ARTIFICIAL repository.

Scores computed here are meaningless and must never be reported as model performance.
"""

import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

import compassio_ml.modeling.final_eval as fe
from compassio_ml.modeling.data import load_partitions
from compassio_ml.modeling.frozen import FrozenPaths, sha256_file, write_lock

CLIMATE = ["solar power plant", "wind farm", "hydropower station", "drought resilience"]
OTHER = ["school building", "hospital equipment", "road paving", "stadium construction"]


def make_repo(root: Path, *, pk_in_train: bool = False) -> FrozenPaths:
    rng = np.random.default_rng(1)
    rows, membership = [], []
    rid = 0
    for g in range(150):
        positive = g % 3 == 0
        part = (["train"] * 6 + ["validation"] * 2 + ["test"] * 2)[g % 10]
        pk = g % 11 == 0
        for _ in range(int(rng.integers(1, 3))):
            rid += 1
            w = rng.choice(CLIMATE if positive else OTHER, size=2)
            rows.append(
                {
                    "record_id": str(rid),
                    "is_climate_related": positive,
                    "rio_overall": (2 if g % 2 else 1) if positive else 0,
                    "rio_mitigation": 1 if positive and g % 4 else 0,
                    "rio_adaptation": 1 if positive and not g % 4 else 0,
                    "title_clean": f"Example {w[0]} {g}",
                    "description_clean": f"Example {w[0]} and {w[1]}.",
                    "commitment_year": 2000 + g % 22,
                    "recipient_iso3": "PAK" if pk else "EXL",
                    "recipient": "Pakistan" if pk else "Exampleland",
                    "sector_name": "ENERGY" if positive and g % 2 else "OTHER",
                    "is_pakistan": pk,
                    "retrospective_text_warning": g % 3 == 1,
                    "amount_original": 1.0,
                    "eligibility_status": "eligible",
                    "leakage_group_id": f"g{g:03d}",
                }
            )
            pk_split = "test" if pk else ("validation" if part == "test" else part)
            if pk_in_train and pk and g % 2 == 0:  # some Pakistan rows leak into train
                pk_split = "train"
            membership.append(
                {
                    "record_id": str(rid),
                    "leakage_group_id": f"g{g:03d}",
                    "eligibility_status": "eligible",
                    "split_primary": part,
                    "split_chronological": part,
                    "split_pakistan_holdout": pk_split,
                }
            )
    (root / "data").mkdir(parents=True)
    paths = FrozenPaths(
        root / "data/t.parquet",
        root / "data/m.parquet",
        root / "data/c.yaml",
        root / "data/lock.json",
    )
    pd.DataFrame(rows).to_parquet(paths.table, index=False)
    pd.DataFrame(membership).to_parquet(paths.membership, index=False)
    paths.split_config.write_text("version: example\n", encoding="utf-8")
    write_lock(paths)
    return paths


SPEC = {
    "algorithm": "logistic_regression",
    "representation": "title_description",
    "tfidf": {"ngram_range": [1, 2], "min_df": 1, "max_df": 1.0, "max_features": None},
    "params": {"C": 16.0, "class_weight": "balanced"},
    "input_columns": ["title_clean", "description_clean"],
    "positive_label": "rio_overall > 0",
}


def write_plan(root: Path, paths: FrozenPaths, **over: Any) -> tuple[Path, str]:
    lock = json.loads(paths.lock.read_text(encoding="utf-8"))
    test_counts = {p: lock["split_counts"][p]["test"] for p in fe.PROTOCOLS}
    plan: dict[str, Any] = {
        "plan_version": "example_plan",
        "source_git_commit": "0" * 40,
        "seed": 5,
        "selected_model": SPEC,
        "data_checksums": {
            "table_sha256": lock["table"]["sha256"],
            "membership_sha256": lock["membership"]["sha256"],
        },
        "protocols": {
            p: {
                "fit_partition": "train",
                "threshold": 0.5,
                "threshold_source": "example",
                "expected_test_records": test_counts[p],
            }
            for p in fe.PROTOCOLS
        },
        "metrics": {},
        "slices": {
            "min_records": 5,
            "min_positives": 2,
            "year_bands": [[2000, 2010], [2011, 2021]],
        },
        "confidence_intervals": {"resamples": 50, "confidence": 0.95},
        "latency_benchmark": {"texts": 20, "repeats": 2},
        "acceptance_criteria": {},
        "baselines": ["keyword", "majority"],
    }
    plan.update(over)
    path = root / "plan.yaml"
    path.write_text(yaml.safe_dump(plan, sort_keys=True), encoding="utf-8")
    return path, sha256_file(path)


def evaluate(
    root: Path, paths: FrozenPaths, protocol: str = "primary", **kw: Any
) -> fe.FinalResult:
    plan, sha = write_plan(root, paths)
    return fe.final_evaluate(protocol, plan, sha, root, root / "out", paths, check_git=False, **kw)


def test_plan_hash_must_match(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    plan, _ = write_plan(tmp_path, paths)

    with pytest.raises(fe.PlanIntegrityError, match="plan sha256"):
        fe.final_evaluate(
            "primary", plan, "f" * 64, tmp_path, tmp_path / "out", paths, check_git=False
        )
    assert not (tmp_path / "out").exists()  # refused before any test access record


def test_data_checksum_must_match_plan(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    plan, sha = write_plan(tmp_path, paths, data_checksums={"table_sha256": "0" * 64})

    with pytest.raises(fe.PlanIntegrityError, match="table_sha256"):
        fe.final_evaluate("primary", plan, sha, tmp_path, tmp_path / "out", paths, check_git=False)


def test_one_shot_access_and_read_only_outputs(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    result = evaluate(tmp_path, paths)

    record = json.loads((result.out_dir / "test_access.json").read_text(encoding="utf-8"))
    assert record["status"] == "completed"
    assert set(record["output_sha256"]) == {
        "model.joblib",
        "results.json",
        "test_predictions.parquet",
    }
    for p in result.out_dir.iterdir():
        assert not p.stat().st_mode & stat.S_IWRITE, p.name
    with pytest.raises(fe.OneShotViolationError):
        evaluate(tmp_path, paths)


def test_failure_is_recorded_and_still_blocks_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_repo(tmp_path)

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("example injected failure")

    monkeypatch.setattr(fe, "_evaluate", boom)
    with pytest.raises(RuntimeError):
        evaluate(tmp_path, paths)
    record = json.loads((tmp_path / "out/primary/test_access.json").read_text(encoding="utf-8"))
    assert record["status"] == "failed" and "example injected failure" in record["error"]
    with pytest.raises(fe.OneShotViolationError):
        evaluate(tmp_path, paths)


def test_expected_test_size_mismatch_fails(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    lock = json.loads(paths.lock.read_text(encoding="utf-8"))
    protocols = {
        p: {
            "fit_partition": "train",
            "threshold": 0.5,
            "threshold_source": "x",
            "expected_test_records": lock["split_counts"][p]["test"] + 1,
        }
        for p in fe.PROTOCOLS
    }
    plan, sha = write_plan(tmp_path, paths, protocols=protocols)

    with pytest.raises(fe.PlanIntegrityError, match="plan expects"):
        fe.final_evaluate("primary", plan, sha, tmp_path, tmp_path / "out", paths, check_git=False)


def test_pakistan_leakage_into_training_is_refused(tmp_path: Path) -> None:
    paths = make_repo(tmp_path, pk_in_train=True)

    with pytest.raises(fe.PlanIntegrityError, match="Pakistan records present"):
        evaluate(tmp_path, paths, protocol="pakistan_holdout")


def test_pakistan_confusions_and_counts(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    result = evaluate(tmp_path, paths, protocol="pakistan_holdout")

    pk = result.results["pakistan_confusion"]
    test = load_partitions(
        paths.table, paths.membership, "pakistan_holdout", ("test",), allow_test=True
    )["test"]
    energy = (test.meta["sector_name"] == "ENERGY").to_numpy()
    assert (
        pk["all"]["records"] == len(test) == pk["energy"]["records"] + pk["non_energy"]["records"]
    )
    assert pk["energy"]["records"] == int(energy.sum())
    assert pk["all"]["positives"] == int(test.y.sum())
    assert test.meta["is_pakistan"].all()


def test_fit_uses_train_only_and_metrics_are_consistent(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    result = evaluate(tmp_path, paths)

    m = result.results["model"]
    lock = json.loads(paths.lock.read_text(encoding="utf-8"))
    assert result.results["train_records"] == lock["split_counts"]["primary"]["train"]
    assert m["tp"] + m["fp"] + m["fn"] + m["tn"] == m["records"]
    assert m["tp"] + m["fn"] == m["positives"]
    lo, hi = m["average_precision_ci95"]
    assert lo <= m["average_precision"] <= hi
    s = result.results["slices"]
    assert s["energy"]["records"] + s["non_energy"]["records"] == m["records"]
    assert (
        s["positives_significant_overall_1"]["positives"]
        + s["positives_principal_overall_2"]["positives"]
    ) == m["positives"]


def test_fingerprint_is_stable_and_identifies_the_model(tmp_path: Path) -> None:
    paths = make_repo(tmp_path)
    train = load_partitions(paths.table, paths.membership, "primary", ("train",))["train"]
    spec = fe.SelectedModel.model_validate(SPEC)

    a = fe.model_fingerprint(fe.fit_selected(spec, train, 5))
    b = fe.model_fingerprint(fe.fit_selected(spec, train, 5))
    other = fe.SelectedModel.model_validate(
        {**SPEC, "params": {"C": 1.0, "class_weight": "balanced"}}
    )
    c = fe.model_fingerprint(fe.fit_selected(other, train, 5))

    assert a == b != c
    assert fe.train_oof_threshold(spec, train, 5) == fe.train_oof_threshold(spec, train, 5)


def test_code_change_after_plan_commit_is_detected(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "example@example.invalid")
    git("config", "user.name", "Example")
    guarded = tmp_path / "packages/compassio_ml/src/example.py"
    guarded.parent.mkdir(parents=True)
    guarded.write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "example")
    commit = git("rev-parse", "HEAD")

    assert fe.verify_code_unchanged(tmp_path, commit) == commit
    guarded.write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(fe.PlanIntegrityError, match=r"changed since|uncommitted"):
        fe.verify_code_unchanged(tmp_path, commit)
    git("commit", "-qam", "change")
    with pytest.raises(fe.PlanIntegrityError, match="changed since"):
        fe.verify_code_unchanged(tmp_path, commit)
