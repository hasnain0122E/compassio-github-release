"""Release building and safe loading on an ARTIFICIAL repository (never real performance)."""

import json
from pathlib import Path

import pytest

import compassio_ml.modeling.final_eval as fe
from compassio_ml.modeling.frozen import sha256_file
from compassio_ml.modeling.release import (
    MODEL_VERSION,
    EmptyInputError,
    ReleasedClassifier,
    ReleaseError,
    build_release,
    evaluate_acceptance,
)

from .test_final_eval import make_repo, write_plan

CRITERIA = {
    "min_f1": 0.0,
    "min_energy_recall": 0.0,
    "max_ece": 1.0,
    "non_energy_recall_limitation_below": 0.6,
}


@pytest.fixture
def release(tmp_path: Path) -> tuple[Path, Path]:
    paths = make_repo(tmp_path)
    plan_path, sha = write_plan(tmp_path, paths)
    fe.final_evaluate("primary", plan_path, sha, tmp_path, tmp_path / "out", paths, check_git=False)
    plan = fe.load_plan(plan_path, sha)
    results = json.loads((tmp_path / "out/primary/results.json").read_text(encoding="utf-8"))
    acceptance = evaluate_acceptance(results, CRITERIA)
    out = tmp_path / "release"
    manifest = build_release(tmp_path / "out", plan, sha, out, acceptance)
    trusted = tmp_path / "trusted.json"
    trusted.write_text(json.dumps({MODEL_VERSION: manifest["artifact_sha256"]}), encoding="utf-8")
    return out, trusted


def test_release_loads_and_predicts_stably(release: tuple[Path, Path]) -> None:
    out, trusted = release
    first = ReleasedClassifier.load(out, trusted).predict("Example solar power plant", "Example.")
    second = ReleasedClassifier.load(out, trusted).predict("Example solar power plant", "Example.")

    assert first == second
    assert first.model_version == MODEL_VERSION
    assert "not a probability" in first.limitation
    assert 0.0 <= first.label_score <= 1.0
    with pytest.raises(EmptyInputError):
        ReleasedClassifier.load(out, trusted).predict(" ", None)


def test_untrusted_or_tampered_artifacts_are_refused(
    release: tuple[Path, Path], tmp_path: Path
) -> None:
    out, trusted = release
    with pytest.raises(ReleaseError, match="trusted release registry"):
        ReleasedClassifier.load(out, tmp_path / "missing.json")
    artifact = out / "model.joblib"
    artifact.write_bytes(artifact.read_bytes() + b"tamper")
    with pytest.raises(ReleaseError, match="release manifest"):
        ReleasedClassifier.load(out, trusted)


def test_unknown_version_and_schema_fail_safely(release: tuple[Path, Path]) -> None:
    out, trusted = release
    manifest_path = out / "release_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(
        json.dumps({**manifest, "model_version": "example-v9"}), encoding="utf-8"
    )
    with pytest.raises(ReleaseError, match="unknown or incompatible"):
        ReleasedClassifier.load(out, trusted)
    manifest_path.write_text(json.dumps({**manifest, "schema": "other/9"}), encoding="utf-8")
    with pytest.raises(ReleaseError, match="schema"):
        ReleasedClassifier.load(out, trusted)


def test_releases_are_immutable_and_require_completed_evaluation(
    release: tuple[Path, Path], tmp_path: Path
) -> None:
    out, _ = release
    paths_plan = tmp_path / "plan.yaml"
    plan = fe.load_plan(paths_plan, sha256_file(paths_plan))
    with pytest.raises(ReleaseError, match="immutable"):
        build_release(tmp_path / "out", plan, sha256_file(paths_plan), out, {"all_passed": True})


def test_acceptance_fails_closed() -> None:
    primary = {
        "model": {"average_precision_ci95": [0.4, 0.6], "f1": 0.5, "ece_10bin": 0.2},
        "slices": {"energy": {"recall": 0.5}, "non_energy": {"recall": 0.3}},
        "baselines": {"keyword": {"average_precision": 0.5}},
    }
    result = evaluate_acceptance(
        primary,
        {
            "min_f1": 0.65,
            "min_energy_recall": 0.85,
            "max_ece": 0.05,
            "non_energy_recall_limitation_below": 0.6,
        },
    )

    assert not result["all_passed"]
    assert {k for k, v in result["checks"].items() if not v["passed"]} == {
        "ap_ci_lower_above_keyword_ap",
        "f1_at_threshold",
        "energy_recall",
        "ece",
    }
    assert result["non_energy_limitation_required"]
