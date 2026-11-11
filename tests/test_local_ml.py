"""LOCAL DATA checks for Task 004 on the real frozen dataset (skipped when it is absent).

Asserts integrity properties (lock, isolation, allowlist, artifact checksum), not model scores.
"""

from pathlib import Path

import pytest

from compassio_ml.modeling.config import load_benchmark_config
from compassio_ml.modeling.data import FinalTestAccessError, load_partitions
from compassio_ml.modeling.frozen import FrozenPaths, verify_frozen
from compassio_ml.modeling.inference import ClimateRelevanceClassifier, EmptyInputError
from compassio_ml.research.inputs import model_input_columns

REPO = Path(__file__).resolve().parents[1]
CONFIG = load_benchmark_config(REPO / "configs" / "ml_benchmark_v1.yaml")
PATHS = FrozenPaths(
    REPO / CONFIG.data.table,
    REPO / CONFIG.data.membership,
    REPO / CONFIG.data.split_config,
    REPO / CONFIG.data.split_lock,
)

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(
        not (PATHS.table.is_file() and PATHS.membership.is_file()),
        reason="research dataset not built",
    ),
]


def test_frozen_inputs_match_lock() -> None:
    report = verify_frozen(PATHS)

    assert report.ok, report.errors


@pytest.mark.parametrize("protocol", ["primary", "chronological", "pakistan_holdout"])
def test_partitions_match_lock_and_are_isolated(protocol: str) -> None:
    lock_counts = verify_frozen(PATHS).lock["split_counts"][protocol]
    parts = load_partitions(PATHS.table, PATHS.membership, protocol)

    for name in ("train", "validation"):
        assert len(parts[name]) == lock_counts[name]
        assert list(parts[name].features.columns) == list(model_input_columns())
    assert set(parts["train"].groups).isdisjoint(parts["validation"].groups)
    if protocol == "pakistan_holdout":
        for name in ("train", "validation"):
            assert not parts[name].meta["is_pakistan"].any()


def test_test_partition_is_refused_on_real_data() -> None:
    with pytest.raises(FinalTestAccessError):
        load_partitions(PATHS.table, PATHS.membership, "primary", ("test",))


MODEL_DIRS = sorted((REPO / "experiments" / "benchmarks").glob("primary__*/model"))


@pytest.mark.skipif(not MODEL_DIRS, reason="no benchmark artifact present")
@pytest.mark.parametrize("model_dir", MODEL_DIRS, ids=lambda p: p.parent.name)
def test_saved_artifact_loads_and_predicts(model_dir: Path) -> None:
    model = ClimateRelevanceClassifier.load(model_dir)

    prediction = model.predict(
        "Example solar photovoltaic power plant", "Example financing for a solar power plant."
    )

    assert prediction.score_kind in {"probability", "decision_score"}
    assert (
        prediction.dataset_version["table_sha256"] == verify_frozen(PATHS).lock["table"]["sha256"]
    )
    with pytest.raises(EmptyInputError):
        model.predict("", "   ")
