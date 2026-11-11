"""Read-only access to the frozen v1 research table and split membership.

Both files are hash-checked against ``configs/research_split_v1.lock.json`` before use, and
only identifier, text, country and split columns are loaded. Records in a v1 **test** partition
of any protocol are marked ``v1_consumed_test``: they may never enter v2 validation or the v2
external test (they were used for the one-shot v1 evaluation).
"""

import json
from pathlib import Path

import pandas as pd

from compassio_ml.external.paths import V2Paths
from compassio_ml.integrity import sha256_file

LOCK_PATH = Path("configs") / "research_split_v1.lock.json"
TABLE_COLUMNS = [
    "record_id",
    "title_clean",
    "description_clean",
    "recipient_iso3",
    "is_climate_related",
    "rio_mitigation",
    "rio_adaptation",
    "sector_name",
    "parent_id",
    "leakage_group_id",
    "eligibility_status",
    "commitment_year",
]
SPLIT_COLUMNS = ["split_primary", "split_chronological", "split_pakistan_holdout"]


class FrozenInputMismatchError(RuntimeError):
    """A v1 frozen file does not match the committed lock."""


def load_v1_research(paths: V2Paths, lock_path: Path | None = None) -> pd.DataFrame:
    data_root = paths.require_input()
    lock = json.loads((lock_path or paths.repo_root / LOCK_PATH).read_text(encoding="utf-8"))
    table = paths.readable(data_root / "processed" / Path(lock["table"]["path"]).name)
    membership = paths.readable(data_root / "processed" / Path(lock["membership"]["path"]).name)
    for path, expected in (
        (table, lock["table"]["sha256"]),
        (membership, lock["membership"]["sha256"]),
    ):
        actual = sha256_file(path)
        if actual != expected:
            raise FrozenInputMismatchError(f"{path}: sha256 {actual} != lock {expected}")
    frame = pd.read_parquet(table, columns=TABLE_COLUMNS)
    splits = pd.read_parquet(membership, columns=["record_id", *SPLIT_COLUMNS])
    merged = frame.merge(splits, on="record_id", how="left", validate="one_to_one")
    merged["v1_consumed_test"] = (merged[SPLIT_COLUMNS] == "test").any(axis=1)
    merged["candidate_id"] = "aiddata:" + merged["record_id"].astype(str)
    return merged
