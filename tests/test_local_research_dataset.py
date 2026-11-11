"""LOCAL DATA integrity checks on the real built research dataset (Task 003).

Skipped unless `uv run compassio-research build` has produced data/processed outputs from the
registered raw files. Checks integrity properties, not hard-coded research results.
"""

from pathlib import Path

import pandas as pd
import pytest

from compassio_ml.data.inventory import build_inventory
from compassio_ml.data.layout import DataLayout
from compassio_ml.data.manifest_io import validate_manifest
from compassio_ml.research.inputs import TARGET_COLUMNS, is_forbidden, model_input_columns
from compassio_ml.research.splits import check_disjoint

ROOT = Path(__file__).resolve().parents[1] / "data"
PROCESSED = ROOT / "processed"
FILES = {
    "table": PROCESSED / "research_projects.parquet",
    "text": PROCESSED / "research_text_originals.parquet",
    "membership": PROCESSED / "research_split_membership_v1.parquet",
}

pytestmark = [
    pytest.mark.local_data,
    pytest.mark.skipif(
        not all(p.is_file() for p in FILES.values()), reason="research dataset not built"
    ),
]
SPLITS = ("split_primary", "split_chronological", "split_pakistan_holdout")


@pytest.fixture(scope="module")
def table() -> pd.DataFrame:
    return pd.read_parquet(FILES["table"])


@pytest.fixture(scope="module")
def membership() -> pd.DataFrame:
    return pd.read_parquet(FILES["membership"])


def test_raw_sources_unchanged_since_registration() -> None:
    layout = DataLayout(ROOT)
    report = validate_manifest(layout, build_inventory(layout))

    assert report.ok, report.errors


def test_one_row_per_record_and_stable_ids(table: pd.DataFrame, membership: pd.DataFrame) -> None:
    assert table["record_id"].is_unique
    assert table["record_id"].notna().all()
    assert set(table["record_id"]) == set(membership["record_id"])
    assert len(table) == len(membership)
    assert table["leakage_group_id"].str.fullmatch(r"g_[0-9a-f]{16}").all()


def test_labels_are_internally_consistent(table: pd.DataFrame) -> None:
    labelled = table[table["rio_overall"].notna()]
    assert labelled["rio_overall"].between(0, 2).all()
    assert (labelled["is_climate_related"] == (labelled["rio_overall"] > 0)).all()
    reconstructed = (
        labelled["rio_overall"].astype(str)
        + ","
        + labelled["rio_mitigation"].astype(str)
        + ","
        + labelled["rio_adaptation"].astype(str)
    )
    assert (reconstructed == labelled["rio_marker_src"]).all()


def test_originals_preserved_for_every_cleaned_value(table: pd.DataFrame) -> None:
    text = pd.read_parquet(FILES["text"]).set_index("record_id")
    joined = table.set_index("record_id").join(text)
    unchanged = joined["description_cleaning_steps"].fillna("") == ""
    assert (
        joined.loc[unchanged, "description_clean"]
        == joined.loc[unchanged, "description_aiddata_src"]
    ).all()
    assert (
        joined["description_aiddata_src"].notna().sum() >= joined["description_clean"].notna().sum()
    )


def test_splits_group_disjoint(membership: pd.DataFrame) -> None:
    for column in SPLITS:
        assert check_disjoint(membership, column) == [], column


def test_only_eligible_records_are_split(membership: pd.DataFrame) -> None:
    not_eligible = membership["eligibility_status"] != "eligible"
    for column in SPLITS:
        assert (membership.loc[not_eligible, column] == "not_eligible").all()


def test_pakistan_never_in_holdout_training(membership: pd.DataFrame) -> None:
    pk = (membership["recipient_iso3"] == "PAK").fillna(False).astype(bool)
    fit = membership["split_pakistan_holdout"].isin(["train", "validation"])
    assert not (pk & fit).any()
    pk_groups = set(membership.loc[pk, "leakage_group_id"])
    assert pk_groups.isdisjoint(set(membership.loc[fit, "leakage_group_id"]))


def test_chronological_periods_respected(membership: pd.DataFrame) -> None:
    periods = {"train": (2000, 2015), "validation": (2016, 2017), "test": (2018, 2021)}
    for split, (lo, hi) in periods.items():
        years = membership.loc[membership["split_chronological"] == split, "commitment_year"]
        assert years.between(lo, hi).all(), split


def test_model_inputs_exist_and_exclude_targets(table: pd.DataFrame) -> None:
    inputs = model_input_columns(include_context=True)
    assert set(inputs) <= set(table.columns)
    assert not set(inputs) & set(TARGET_COLUMNS)
    assert all(is_forbidden(c) for c in TARGET_COLUMNS)
