"""Join, eligibility, split protocols and input allowlist over ARTIFICIAL records.

All values are invented examples that exercise logic only; they are not observations.
"""

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from compassio_ml.research.dataset import (
    ANALYTICS_ONLY,
    ELIGIBLE,
    QUARANTINED,
    JoinIntegrityError,
    assign_eligibility,
    build_research_table,
    join_research_aiddata,
)
from compassio_ml.research.inputs import (
    CONTEXT_INPUTS,
    TARGET_COLUMNS,
    TEXT_INPUTS,
    is_forbidden,
    model_input_columns,
)
from compassio_ml.research.pipeline import add_groups
from compassio_ml.research.splits import (
    EXCLUDED_PK_GROUP_MATE,
    EXCLUDED_SPANNING,
    NOT_ELIGIBLE,
    SplitConfig,
    build_membership,
    check_disjoint,
    load_split_config,
)

REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO / "configs" / "research_split_v1.yaml"


def research_row(rid: str, marker: str = "0,0,0", **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ID": rid,
        "AidData_Record_ID": rid,
        "Commitment_Year": "2010",
        "Recipient": "Exampleland",
        "Recipient_Region": "Example Region",
        "Sector_Name": "EXAMPLE SECTOR",
        "Flow_Type": "Grant",
        "Funding_Agencies": "Example Agency",
        "Funding_Agencies_Type": "Government Agency",
        "Title": f"Example title {rid}",
        "Description": f"Example description number {rid} with enough words to classify.",
        "Amount_Constant_USD_2021": "100",
        "rio_marker": marker,
    }
    row.update(over)
    return row


def aiddata_row(rid: str, **over: object) -> dict[str, object]:
    row: dict[str, object] = {
        "AidData Record ID": rid,
        "AidData Parent ID": None,
        "Title": f"Example title {rid}",
        "Description": f"Example description number {rid} with enough words to classify.",
        "Commitment Year": "2010",
        "Commitment Date (MM/DD/YYYY)": "2010-05-01T00:00:00",
        "Commitment Date Estimated": "No",
        "Recipient": "Exampleland",
        "Recipient ISO-3": "EXL",
        "Recipient Region": "Example Region",
        "Sector Code": "999",
        "Sector Name": "EXAMPLE SECTOR",
        "Flow Type": "Grant",
        "Flow Type Simplified": "Grant",
        "Flow Class": "ODA-like",
        "Intent": "Development",
        "Status": "Completion",
        "Funding Agencies": "Example Agency",
        "Funding Agencies Type": "Government Agency",
        "Recommended For Aggregates": "Yes",
        "Umbrella": "No",
        "Amount (Original Currency)": "100",
        "Original Currency": "USD",
        "Amount (Constant USD 2021)": "100",
        "Amount Estimated": None,
    }
    row.update(over)
    return row


def frames(
    research: list[dict[str, object]], aiddata: list[dict[str, object]]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.DataFrame(research, dtype=object), pd.DataFrame(aiddata, dtype=object)


def build_table(
    research: list[dict[str, object]], aiddata: list[dict[str, object]]
) -> pd.DataFrame:
    joined, _ = join_research_aiddata(*frames(research, aiddata))
    table, _ = build_research_table(joined, "0" * 64, "1" * 64)
    return assign_eligibility(table)


# ---------------------------------------------------------------- join
def test_one_to_one_join_and_report() -> None:
    research, aiddata = frames(
        [research_row("1"), research_row("2", Title="Example title 2 truncated")],
        [aiddata_row("1"), aiddata_row("2"), aiddata_row("3")],
    )

    joined, report = join_research_aiddata(research, aiddata)

    assert len(joined) == 2
    assert report.matched == 2
    assert report.research_only == []
    assert report.aiddata_only == ["3"]
    assert report.field_mismatches["Title"] == 1
    assert report.field_mismatches["Recipient"] == 0


@pytest.mark.parametrize("side", ["research", "aiddata"])
def test_join_refuses_duplicate_or_missing_keys(side: str) -> None:
    research = [research_row("1"), research_row("2")]
    aiddata = [aiddata_row("1"), aiddata_row("2")]
    if side == "research":
        research.append(research_row("1"))
    else:
        aiddata.append(aiddata_row(""))

    with pytest.raises(JoinIntegrityError):
        join_research_aiddata(*frames(research, aiddata))


def test_cleaning_keeps_originals_and_flags_research_truncation() -> None:
    long_title = "Example " + "very long title " * 20  # > 255 characters
    joined, _ = join_research_aiddata(
        *frames(
            [research_row("1", Title=long_title[:255])],
            [
                aiddata_row(
                    "1", Title=long_title, Description="  Example  text  with  spaces here ok "
                )
            ],
        )
    )

    table, originals = build_research_table(joined, "0" * 64, "1" * 64)

    row = table.iloc[0]
    assert row["title_clean"] == long_title.strip()
    assert bool(row["research_title_truncated_255"])
    assert row["description_clean"] == "Example text with spaces here ok"
    assert row["description_cleaning_steps"] == "whitespace_normalized"
    assert originals.iloc[0]["description_aiddata_src"] == "  Example  text  with  spaces here ok "
    assert originals.iloc[0]["title_research_src"] == long_title[:255]
    assert row["research_file_sha256"] == "0" * 64


def test_labels_and_finance_fields_are_parsed_not_imputed() -> None:
    table = build_table(
        [research_row("1", "2,0,2"), research_row("2", Amount_Constant_USD_2021=None)],
        [
            aiddata_row("1"),
            aiddata_row(
                "2",
                **{
                    "Amount (Original Currency)": None,
                    "Original Currency": None,
                    "Amount (Constant USD 2021)": None,
                },
            ),
        ],
    )

    first, second = table.iloc[0], table.iloc[1]
    assert (first["rio_overall"], first["rio_mitigation"], first["rio_adaptation"]) == (2, 0, 2)
    assert bool(first["is_climate_related"])
    assert first["rio_marker_src"] == "2,0,2"
    assert pd.isna(second["amount_original"]) and pd.isna(second["amount_currency"])
    assert second["eligibility_status"] == ELIGIBLE  # missing money does not block text use


# ---------------------------------------------------------------- eligibility
def test_conflicting_labels_on_identical_description_are_quarantined() -> None:
    shared = "Identical example description shared by package members for testing."
    table = build_table(
        [
            research_row("1", "1,1,0", Description=shared),
            research_row("2", "0,0,0", Description=shared),
            research_row("3", "0,0,0"),
        ],
        [
            aiddata_row("1", Description=shared),
            aiddata_row("2", Description=shared),
            aiddata_row("3"),
        ],
    )

    status = dict(zip(table["record_id"], table["eligibility_status"], strict=True))
    assert status == {"1": QUARANTINED, "2": QUARANTINED, "3": ELIGIBLE}
    assert table.loc[table["record_id"] == "1", "rio_marker_src"].item() == "1,1,0"  # label kept


def test_invalid_label_quarantined_and_short_text_analytics_only() -> None:
    table = build_table(
        [
            research_row("1", "9,9,9"),
            research_row("2", Description="Too short."),
            research_row("3"),
        ],
        [aiddata_row("1"), aiddata_row("2", Description="Too short."), aiddata_row("3")],
    )

    by_id = table.set_index("record_id")
    assert by_id.loc["1", "eligibility_status"] == QUARANTINED
    assert "invalid_or_missing_rio_marker" in str(by_id.loc["1", "exclusion_reasons"])
    assert by_id.loc["2", "eligibility_status"] == ANALYTICS_ONLY
    assert by_id.loc["2", "exclusion_reasons"] == "insufficient_description"
    assert by_id.loc["2", "is_climate_related"] is not None  # not converted into a negative
    assert len(table) == 3  # nothing dropped


# ---------------------------------------------------------------- splits
def synthetic_table(n: int = 300) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "record_id": str(i),
                "leakage_group_id": f"g{i // 3}",  # groups of 3
                "eligibility_status": QUARANTINED if i % 50 == 0 else ELIGIBLE,
                "is_climate_related": i % 7 == 0,
                "commitment_year": 2000 + (i // 3) % 22,
                "recipient_iso3": "PAK" if i % 30 in (1, 2) else "EXL",
                "sector_name": "ENERGY" if i % 4 == 0 else "OTHER",
            }
        )
    frame = pd.DataFrame(rows)
    # one group spanning two chronological periods
    frame.loc[frame["record_id"] == "5", "commitment_year"] = 2019
    return frame


@pytest.fixture(scope="module")
def config() -> SplitConfig:
    return load_split_config(CONFIG_PATH)


def test_frozen_config_loads(config: SplitConfig) -> None:
    assert config.version == "research_split_v1"
    assert config.chronological.periods["train"] == (2000, 2015)
    assert config.pakistan_holdout.holdout_iso3 == "PAK"


def test_primary_split_is_group_disjoint_and_covers_eligible(config: SplitConfig) -> None:
    table = synthetic_table()
    m = build_membership(table, config)

    assert check_disjoint(m, "split_primary") == []
    eligible = m["eligibility_status"] == ELIGIBLE
    assert set(m.loc[eligible, "split_primary"]) == {"train", "validation", "test"}
    assert (m.loc[~eligible, "split_primary"] == NOT_ELIGIBLE).all()
    pos = m[eligible & m["is_climate_related"]]
    assert set(pos["split_primary"]) == {"train", "validation", "test"}  # stratification


def test_chronological_cutoffs_and_spanning_groups(config: SplitConfig) -> None:
    m = build_membership(synthetic_table(), config)

    assert check_disjoint(m, "split_chronological") == []
    span = m[m["leakage_group_id"] == "g1"]
    assert set(span["split_chronological"]) == {EXCLUDED_SPANNING}
    for split, (lo, hi) in config.chronological.periods.items():
        years = m.loc[m["split_chronological"] == split, "commitment_year"]
        assert years.between(lo, hi).all()


def test_pakistan_holdout_isolation(config: SplitConfig) -> None:
    table = synthetic_table()
    m = build_membership(table, config)

    pk = m["recipient_iso3"] == "PAK"
    eligible = m["eligibility_status"] == ELIGIBLE
    assert (m.loc[pk & eligible, "split_pakistan_holdout"] == "test").all()
    assert not (m.loc[~pk, "split_pakistan_holdout"] == "test").any()
    pk_groups = set(m.loc[pk, "leakage_group_id"])
    train_groups = set(
        m.loc[m["split_pakistan_holdout"].isin(["train", "validation"]), "leakage_group_id"]
    )
    assert pk_groups.isdisjoint(train_groups)
    mates = m[(~pk) & m["leakage_group_id"].isin(pk_groups) & eligible]
    assert (mates["split_pakistan_holdout"] == EXCLUDED_PK_GROUP_MATE).all() and len(mates) > 0


def test_splits_are_reproducible_and_seed_dependent(config: SplitConfig) -> None:
    table = synthetic_table()
    first = build_membership(table, config)
    second = build_membership(table.sample(frac=1, random_state=0), config)

    merged = first.merge(second, on="record_id", suffixes=("", "_2"))
    for col in ("split_primary", "split_chronological", "split_pakistan_holdout"):
        assert (merged[col] == merged[f"{col}_2"]).all()
    other_seed = build_membership(table, config.model_copy(update={"seed": config.seed + 1}))
    assert not (other_seed["split_primary"] == first["split_primary"]).all()


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["primary"].update(
            {"fractions": {"train": 0.8, "validation": 0.1, "test": 0.2}}
        ),
        lambda d: d["primary"].update({"fractions": {"train": 0.85, "test": 0.15}}),
        lambda d: d["chronological"]["periods"].update({"validation": [2015, 2017]}),
        lambda d: d["pakistan_holdout"].update({"holdout_iso3": "Pakistan"}),
        lambda d: d.update({"unexpected": 1}),
    ],
)
def test_invalid_configs_rejected(mutate: object) -> None:
    import yaml

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(data)  # type: ignore[operator]
    with pytest.raises(ValidationError):
        SplitConfig.model_validate(data)


def test_grouping_integrates_with_table() -> None:
    shared = "Identical example description shared by two records for testing purposes."
    table = build_table(
        [
            research_row("1", Description=shared),
            research_row("2", Description=shared),
            research_row("3"),
        ],
        [
            aiddata_row("1", Description=shared),
            aiddata_row("2", Description=shared),
            aiddata_row("3", **{"AidData Parent ID": "P1"}),
        ],
    )

    grouped, relations = add_groups(table)

    gid = dict(zip(grouped["record_id"], grouped["leakage_group_id"], strict=True))
    assert gid["1"] == gid["2"] != gid["3"]
    assert relations["description"] == [("1", "2")]


# ---------------------------------------------------------------- model input allowlist
def test_input_allowlist_excludes_labels_and_future_fields() -> None:
    for column in model_input_columns(include_context=True):
        assert not is_forbidden(column), column
    for column in TARGET_COLUMNS:
        assert is_forbidden(column), column
    for column in (
        "sdg13",
        "staff_comments",
        "completion_year",
        "implementation_start_year",
        "retrospective_text_warning",
        "leakage_group_id",
        "split_primary",
        "eligibility_status",
        "commitment_year",
        "parent_id",
        "status",
    ):
        assert is_forbidden(column), column
    assert set(TEXT_INPUTS) <= set(model_input_columns())
    assert not set(CONTEXT_INPUTS) & set(model_input_columns())


def test_allowlist_columns_exist_in_built_table() -> None:
    table = build_table([research_row("1")], [aiddata_row("1")])

    assert set(model_input_columns(include_context=True)) <= set(table.columns)
    leaked = [c for c in model_input_columns(include_context=True) if c in TARGET_COLUMNS]
    assert leaked == []
