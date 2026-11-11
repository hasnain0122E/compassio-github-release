"""Error taxonomy logic on ARTIFICIAL rows (never real metrics)."""

from pathlib import Path

import pandas as pd
import pytest

from compassio_ml.modeling.error_analysis import (
    NotValidationDataError,
    analyse,
    error_tags,
    load_validation_predictions,
    outcome,
)


def test_outcome_labels() -> None:
    assert [outcome(1, 1), outcome(0, 1), outcome(1, 0), outcome(0, 0)] == ["TP", "FP", "FN", "TN"]


def test_false_negative_tags() -> None:
    tags = error_tags(
        {
            "outcome": "FN",
            "sector_name": "WATER SUPPLY",
            "description_clean": "Example short text",
            "keyword_hits": 0,
            "rio_overall": 1,
            "rio_mitigation": 0,
            "rio_adaptation": 1,
            "retrospective_text_warning": True,
        }
    )

    assert tags == [
        "adaptation_only_label",
        "significant_not_principal",
        "non_energy_sector",
        "no_climate_keyword",
        "short_description",
        "retrospective_wording",
    ]


def test_false_positive_tags_and_true_outcomes_untagged() -> None:
    fp = error_tags(
        {
            "outcome": "FP",
            "sector_name": "ENERGY",
            "description_clean": "x" * 400,
            "keyword_hits": 2,
            "label_revealing_terms": True,
        }
    )

    assert fp == ["energy_sector", "climate_keyword_present", "explicit_climate_vocabulary"]
    assert error_tags({"outcome": "TP"}) == []


def _write(tmp_path: Path, split: str) -> tuple[Path, Path, Path]:
    run = tmp_path / "run"
    run.mkdir()
    pd.DataFrame(
        {
            "record_id": ["1", "2"],
            "leakage_group_id": ["g1", "g2"],
            "y_true": [1, 0],
            "score": [0.2, 0.9],
            "pred_at_selected_threshold": [0, 1],
        }
    ).to_parquet(run / "winner_validation_predictions.parquet")
    table = tmp_path / "t.parquet"
    pd.DataFrame(
        {
            "record_id": ["1", "2", "3"],
            "title_clean": ["Example irrigation canal", "Example solar plant", "Example test row"],
            "description_clean": [
                "Example irrigation works.",
                "Example solar plant loan.",
                "hidden",
            ],
            "sector_name": ["AGRICULTURE", "ENERGY", "HEALTH"],
            "flow_type": ["Grant"] * 3,
            "commitment_year": [2010] * 3,
            "recipient_iso3": ["EXL"] * 3,
            "is_pakistan": [False] * 3,
            "rio_overall": [1, 0, 0],
            "rio_mitigation": [0, 0, 0],
            "rio_adaptation": [1, 0, 0],
            "retrospective_text_warning": [False, True, False],
            "retrospective_signals": [""] * 3,
            "label_revealing_terms": [False] * 3,
        }
    ).to_parquet(table)
    membership = tmp_path / "m.parquet"
    pd.DataFrame(
        {"record_id": ["1", "2", "3"], "split_primary": [split, "validation", "test"]}
    ).to_parquet(membership)
    return run, table, membership


def test_analysis_uses_validation_rows_only(tmp_path: Path) -> None:
    run, table, membership = _write(tmp_path, "validation")

    result = analyse(load_validation_predictions(run, table, membership))

    assert set(result.records["record_id"]) == {"1", "2"}  # the test row "3" is never joined
    assert dict(zip(result.records["record_id"], result.records["outcome"], strict=True)) == {
        "1": "FN",
        "2": "FP",
    }
    assert set(result.tag_summary["outcome"]) == {"FN", "FP"}


def test_predictions_outside_validation_are_refused(tmp_path: Path) -> None:
    run, table, membership = _write(tmp_path, "test")

    with pytest.raises(NotValidationDataError):
        load_validation_predictions(run, table, membership)
