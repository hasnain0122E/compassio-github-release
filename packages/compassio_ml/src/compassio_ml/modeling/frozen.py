"""Integrity lock for the frozen Task 003 dataset and split membership.

``configs/research_split_v1.lock.json`` (committed) records the SHA-256 of the split config and
of the two Parquet files, plus per-protocol split counts. Every benchmark run verifies the
current files against it and refuses to continue on any difference, so a split can never be
silently regenerated to obtain better scores.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

SPLIT_COLUMNS = ("split_primary", "split_chronological", "split_pakistan_holdout")
PROTOCOL_COLUMN = {
    "primary": "split_primary",
    "chronological": "split_chronological",
    "pakistan_holdout": "split_pakistan_holdout",
}
LOCK_VERSION = 1


class FrozenDataError(RuntimeError):
    """The dataset or split membership does not match the committed lock."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenPaths:
    table: Path
    membership: Path
    split_config: Path
    lock: Path


def _split_counts(membership: pd.DataFrame) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for protocol, column in PROTOCOL_COLUMN.items():
        counts = membership[column].value_counts().sort_index()
        out[protocol] = {str(k): int(v) for k, v in counts.items()}
    return out


def build_lock(paths: FrozenPaths) -> dict[str, object]:
    membership = pd.read_parquet(paths.membership)
    return {
        "lock_version": LOCK_VERSION,
        "split_config": {
            "path": paths.split_config.as_posix(),
            "sha256": sha256_file(paths.split_config),
        },
        "table": {"path": paths.table.as_posix(), "sha256": sha256_file(paths.table)},
        "membership": {
            "path": paths.membership.as_posix(),
            "sha256": sha256_file(paths.membership),
        },
        "split_counts": _split_counts(membership),
    }


def write_lock(paths: FrozenPaths) -> dict[str, object]:
    lock = build_lock(paths)
    paths.lock.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lock


@dataclass
class FrozenReport:
    lock: dict[str, Any]
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def verify_frozen(paths: FrozenPaths) -> FrozenReport:
    """Compare current files with the committed lock (hashes and split counts)."""
    if not paths.lock.is_file():
        raise FrozenDataError(f"Split lock not found: {paths.lock}")
    lock = json.loads(paths.lock.read_text(encoding="utf-8"))
    report = FrozenReport(lock=lock)
    for key, path in (
        ("split_config", paths.split_config),
        ("table", paths.table),
        ("membership", paths.membership),
    ):
        if not path.is_file():
            report.errors.append(f"{key}: file missing: {path}")
            continue
        actual = sha256_file(path)
        expected = lock[key]["sha256"]
        if actual != expected:
            report.errors.append(f"{key}: sha256 {actual} != locked {expected} ({path})")
    if report.ok:
        counts = _split_counts(pd.read_parquet(paths.membership))
        if counts != lock["split_counts"]:
            report.errors.append(
                f"split counts differ from lock: {counts} != {lock['split_counts']}"
            )
    return report


def require_frozen(paths: FrozenPaths) -> FrozenReport:
    report = verify_frozen(paths)
    if not report.ok:
        raise FrozenDataError(
            "Frozen Task 003 inputs changed; refusing to run. A changed split needs a new "
            "version (research_split_v2) and a new lock:\n  " + "\n  ".join(report.errors)
        )
    return report
