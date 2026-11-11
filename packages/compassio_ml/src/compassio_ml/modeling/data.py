"""Protocol-aware loading of training/validation data with a hard test-partition guard.

Model features come exclusively from ``compassio_ml.research.inputs.model_input_columns()``.
Slice metadata (year, sector, country, amounts, warnings) is returned in a *separate* frame that
is never passed to an estimator.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from compassio_ml.modeling.frozen import PROTOCOL_COLUMN
from compassio_ml.research.inputs import TARGET_COLUMNS, is_forbidden, model_input_columns

TARGET = "is_climate_related"
FIT_PARTITIONS = frozenset({"train", "validation"})
SLICE_COLUMNS = (
    "commitment_year",
    "recipient_iso3",
    "recipient",
    "sector_name",
    "is_pakistan",
    "retrospective_text_warning",
    "amount_original",
)


class FinalTestAccessError(PermissionError):
    """A Task 004 code path tried to read a frozen test partition."""


@dataclass(frozen=True)
class Partition:
    """One protocol partition. ``features`` holds only allow-listed input columns."""

    name: str
    record_ids: np.ndarray
    groups: np.ndarray
    features: pd.DataFrame
    y: np.ndarray
    meta: pd.DataFrame

    def __len__(self) -> int:
        return len(self.record_ids)

    @property
    def positives(self) -> int:
        return int(self.y.sum())


def _check_feature_columns(columns: tuple[str, ...]) -> None:
    bad = [c for c in columns if is_forbidden(c) or c in TARGET_COLUMNS]
    if bad:
        raise ValueError(f"Forbidden feature columns requested: {bad}")


def load_partitions(
    table_path: Path,
    membership_path: Path,
    protocol: str,
    partitions: tuple[str, ...] = ("train", "validation"),
    *,
    allow_test: bool = False,
) -> dict[str, Partition]:
    """Load eligible records of the requested partitions for ``protocol``.

    Raises ``FinalTestAccessError`` for ``test`` unless ``allow_test`` is set; Task 004 never
    sets it. Test rows are filtered out before any feature column is materialised.
    """
    if protocol not in PROTOCOL_COLUMN:
        raise ValueError(f"Unknown protocol {protocol!r}; choose from {sorted(PROTOCOL_COLUMN)}")
    requested = set(partitions)
    if "test" in requested and not allow_test:
        raise FinalTestAccessError(
            "Task 004 is validation-only: the frozen test partition may not be loaded"
        )
    unknown = requested - FIT_PARTITIONS - {"test"}
    if unknown:
        raise ValueError(f"Unknown partitions: {sorted(unknown)}")

    split_column = PROTOCOL_COLUMN[protocol]
    membership = pd.read_parquet(
        membership_path,
        columns=["record_id", "leakage_group_id", "eligibility_status", split_column],
    )
    membership = membership[
        (membership["eligibility_status"] == "eligible") & membership[split_column].isin(requested)
    ]
    feature_columns = model_input_columns(include_context=False)
    _check_feature_columns(feature_columns)
    table = pd.read_parquet(
        table_path, columns=["record_id", TARGET, *feature_columns, *SLICE_COLUMNS]
    )
    table = table[table["record_id"].isin(set(membership["record_id"]))]
    merged = membership.merge(table, on="record_id", how="inner", validate="one_to_one")
    if len(merged) != len(membership):
        raise ValueError("Membership and table disagree on eligible record ids")
    if merged[TARGET].isna().any():
        raise ValueError("Eligible records must all carry a label")

    out: dict[str, Partition] = {}
    for name in sorted(requested):
        part = merged[merged[split_column] == name].sort_values(
            "record_id", key=lambda s: s.astype(int)
        )
        out[name] = Partition(
            name=name,
            record_ids=part["record_id"].astype(str).to_numpy(),
            groups=part["leakage_group_id"].astype(str).to_numpy(),
            features=part[list(feature_columns)].reset_index(drop=True),
            y=part[TARGET].astype(bool).astype(int).to_numpy(),
            meta=part[list(SLICE_COLUMNS)].reset_index(drop=True),
        )
    _assert_disjoint(out)
    return out


def _assert_disjoint(parts: dict[str, Partition]) -> None:
    names = sorted(parts)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if set(parts[a].record_ids) & set(parts[b].record_ids):
                raise ValueError(f"Partitions {a} and {b} share records")
            if set(parts[a].groups) & set(parts[b].groups):
                raise ValueError(f"Partitions {a} and {b} share leakage groups")
