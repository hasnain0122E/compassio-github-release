"""LOCAL DATA: integrity of the recorded Task 006-ML2 run and its development champion.

Skipped when the git-ignored run/candidate are absent. Checks records and guards only; it does
not re-evaluate anything and never reads sealed, external-test or consumed-v1-test data.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from compassio_ml.model_v2.artifact import ExperimentalClassifier
from compassio_ml.model_v2.plan import plan_sha256

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / "data/ml_v2/experiments_v2/fast/ml2fast_49317056_3bf81cd4_20261109T192725Z"
CANDIDATE = REPO / "data/ml_v2/models_v2_dev/ml2fast_49317056_c76204127550"
TRUSTED = REPO / "configs" / "trusted_model_releases.json"

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(not (RUN.is_dir() and CANDIDATE.is_dir()), reason="local ML2 run absent"),
]


def test_run_was_produced_from_a_clean_commit_with_the_frozen_plan() -> None:
    manifest = json.loads((RUN / "run_manifest.json").read_text("utf-8"))

    assert manifest["dirty"] is False
    assert manifest["plan_sha256"] == plan_sha256(REPO / "configs" / "ml_v2_fast_experiment.yaml")
    assert manifest["test_or_sealed_data_loaded"] is False
    assert manifest["consumed_v1_tests_rerun"] is False


def test_selection_and_saved_champion_agree() -> None:
    results = json.loads((RUN / "results.json").read_text("utf-8"))
    manifest = json.loads((CANDIDATE / "candidate_manifest.json").read_text("utf-8"))

    assert results["selection"]["champion"] == f"{manifest['population']}/{manifest['candidate']}"
    assert results["champion_artifact"]["artifact_sha256"] == manifest["artifact_sha256"]
    assert manifest["status"] == "development_candidate"


def test_champion_loads_only_through_guards_and_is_not_a_trusted_release() -> None:
    trusted = json.loads(TRUSTED.read_text("utf-8"))
    model = ExperimentalClassifier.load(CANDIDATE, TRUSTED)

    assert model.manifest["artifact_sha256"] not in trusted.values()
    assert model.predict("example artificial title", "").status == "development_candidate"


def test_predictions_cover_only_development_validation_records() -> None:
    pred = pd.read_parquet(RUN / "valid_predictions.parquet")

    assert len(pred) == 2550 and int(pred["y"].sum()) == 827
    assert pred["candidate_id"].is_unique
    assert set(pred["source_id"]) == {"iati_fcdo", "iati_ec_intpa"}
