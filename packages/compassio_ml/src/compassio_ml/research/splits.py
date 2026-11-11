"""Deterministic, group-disjoint split membership for the three evaluation protocols.

No model is trained here. Assignment is at the level of ``leakage_group_id``: all eligible
members of a group always share one split value within a protocol.

Group ordering uses SHA-256 of ``"{seed}:{protocol}:{group_id}"`` (stable across processes);
groups are then assigned greedily to the split whose filled share of its target row count is
lowest, separately for groups with and without a positive record (``group_has_positive``).
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

SplitName = Literal["train", "validation", "test"]
NOT_ELIGIBLE = "not_eligible"
EXCLUDED_SPANNING = "excluded_spanning_periods"
EXCLUDED_PK_GROUP_MATE = "excluded_pakistan_group_mate"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Population(_Frozen):
    eligible_status: str
    group_key: str
    group_relations: tuple[str, ...]


class PrimaryConfig(_Frozen):
    description: str
    fractions: dict[SplitName, float]
    stratify_by: Literal["group_has_positive"]

    @model_validator(mode="after")
    def _fractions(self) -> "PrimaryConfig":
        _check_fractions(_as_str_keys(self.fractions), {"train", "validation", "test"})
        return self


class ChronologicalConfig(_Frozen):
    description: str
    periods: dict[SplitName, tuple[int, int]]
    spanning_group_policy: Literal["exclude"]

    @model_validator(mode="after")
    def _ordered(self) -> "ChronologicalConfig":
        order = [self.periods[s] for s in ("train", "validation", "test")]
        for lo, hi in order:
            if lo > hi:
                raise ValueError("period start must be <= end")
        for (_, prev_hi), (next_lo, _) in pairwise(order):
            if next_lo <= prev_hi:
                raise ValueError("periods must be strictly increasing and non-overlapping")
        return self


class PakistanConfig(_Frozen):
    description: str
    holdout_iso3: str = Field(pattern=r"^[A-Z]{3}$")
    group_mate_policy: Literal["exclude"]
    train_validation_fractions: dict[Literal["train", "validation"], float]
    stratify_by: Literal["group_has_positive"]
    report_strata: dict[str, str]

    @model_validator(mode="after")
    def _fractions(self) -> "PakistanConfig":
        _check_fractions(_as_str_keys(self.train_validation_fractions), {"train", "validation"})
        return self


class SplitConfig(_Frozen):
    version: str
    seed: int
    population: Population
    primary: PrimaryConfig
    chronological: ChronologicalConfig
    pakistan_holdout: PakistanConfig


def _check_fractions(fractions: Mapping[str, float], names: set[str]) -> None:
    keys = set(fractions)
    if keys != names:
        raise ValueError(f"fractions must define exactly {sorted(names)}, got {sorted(keys)}")
    if any(v <= 0 for v in fractions.values()) or abs(sum(fractions.values()) - 1) > 1e-9:
        raise ValueError("fractions must be positive and sum to 1")


def _as_str_keys[K: str](mapping: Mapping[K, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in mapping.items()}


def load_split_config(path: Path) -> SplitConfig:
    return SplitConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def order_key(seed: int, protocol: str, group_id: str) -> str:
    return hashlib.sha256(f"{seed}:{protocol}:{group_id}".encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GroupStat:
    group_id: str
    rows: int
    has_positive: bool


def assign_groups(
    groups: list[GroupStat], fractions: dict[str, float], *, seed: int, protocol: str
) -> dict[str, str]:
    """Greedy, deterministic, stratified assignment of whole groups to splits."""
    out: dict[str, str] = {}
    names = sorted(fractions)  # deterministic tie-breaking
    for stratum in (True, False):
        members = sorted(
            (g for g in groups if g.has_positive is stratum),
            key=lambda g: order_key(seed, protocol, g.group_id),
        )
        total = sum(g.rows for g in members)
        filled = dict.fromkeys(names, 0)
        for g in members:
            target = {n: fractions[n] * total for n in names}
            choice = min(names, key=lambda n: (filled[n] / target[n] if target[n] else 1.0, n))
            out[g.group_id] = choice
            filled[choice] += g.rows
    return out


def _group_stats(frame: pd.DataFrame) -> list[GroupStat]:
    agg = frame.groupby("leakage_group_id", sort=True).agg(
        rows=("record_id", "size"), has_positive=("is_climate_related", "max")
    )
    return [
        GroupStat(group_id=str(gid), rows=int(rows), has_positive=bool(pos))
        for gid, rows, pos in zip(agg.index, agg["rows"], agg["has_positive"], strict=True)
    ]


def _period_of(year: int, periods: dict[SplitName, tuple[int, int]]) -> str | None:
    for name, (lo, hi) in periods.items():
        if lo <= year <= hi:
            return name
    return None


def build_membership(table: pd.DataFrame, config: SplitConfig) -> pd.DataFrame:
    """Return one row per record with split membership for each protocol.

    ``table`` needs: record_id, leakage_group_id, eligibility_status, is_climate_related,
    commitment_year, recipient_iso3.
    """
    eligible_mask = table["eligibility_status"] == config.population.eligible_status
    eligible = table[eligible_mask]
    membership = table[
        [
            "record_id",
            "leakage_group_id",
            "eligibility_status",
            "is_climate_related",
            "commitment_year",
            "recipient_iso3",
            "sector_name",
        ]
    ].copy()

    # A. primary
    primary = assign_groups(
        _group_stats(eligible),
        _as_str_keys(config.primary.fractions),
        seed=config.seed,
        protocol="primary",
    )
    membership["split_primary"] = [
        primary[g] if ok else NOT_ELIGIBLE
        for g, ok in zip(membership["leakage_group_id"], eligible_mask, strict=True)
    ]

    # B. chronological
    periods = dict(config.chronological.periods)
    group_periods = (
        eligible.assign(_p=eligible["commitment_year"].map(lambda y: _period_of(int(y), periods)))
        .groupby("leakage_group_id")["_p"]
        .agg(lambda s: "|".join(sorted({str(p) for p in s.dropna()})))
    )
    chrono_of: dict[str, str] = {}
    for gid, ps in group_periods.items():
        names = str(ps).split("|") if ps else []
        chrono_of[str(gid)] = names[0] if len(names) == 1 else EXCLUDED_SPANNING
    membership["split_chronological"] = [
        chrono_of.get(g, EXCLUDED_SPANNING) if ok else NOT_ELIGIBLE
        for g, ok in zip(membership["leakage_group_id"], eligible_mask, strict=True)
    ]

    # C. Pakistan holdout
    iso = config.pakistan_holdout.holdout_iso3
    is_holdout = (table["recipient_iso3"] == iso).fillna(False).astype(bool)
    pk_groups = set(table.loc[is_holdout, "leakage_group_id"])
    trainable = eligible[~eligible["leakage_group_id"].isin(pk_groups)]
    pk_train = assign_groups(
        _group_stats(trainable),
        _as_str_keys(config.pakistan_holdout.train_validation_fractions),
        seed=config.seed,
        protocol="pakistan_holdout",
    )
    pk_split: list[str] = []
    for gid, ok, in_holdout in zip(
        membership["leakage_group_id"], eligible_mask, is_holdout, strict=True
    ):
        if not ok:
            pk_split.append(NOT_ELIGIBLE)
        elif in_holdout:
            pk_split.append("test")
        elif gid in pk_groups:
            pk_split.append(EXCLUDED_PK_GROUP_MATE)
        else:
            pk_split.append(pk_train[gid])
    membership["split_pakistan_holdout"] = pk_split
    membership.insert(0, "split_version", config.version)
    return membership.reset_index(drop=True)


def check_disjoint(membership: pd.DataFrame, column: str) -> list[str]:
    """Group ids whose eligible members appear in more than one train/validation/test split."""
    used = membership[membership[column].isin(["train", "validation", "test"])]
    counts = used.groupby("leakage_group_id")[column].nunique()
    return sorted(str(g) for g in counts[counts > 1].index)
