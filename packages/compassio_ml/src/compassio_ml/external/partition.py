"""V2 partition design (``v2_partition_design_v2``), external-test pilot sampling and the
sample-size policy.

Rules are applied to whole **partition groups** (see ``linkage``), in this order:

1. Any member comes from a source restricted for both training and automated evaluation
   (``configs/ml_rights_eligibility_v2.yaml``, e.g. GCF pages: ``ai-train=no``)
   -> ``restricted_reference_only`` (kept for separately authorised reference use; never in a
   pool or worksheet).
2. Any member is an AidData record in a v1 **test** partition (any protocol)
   -> ``excluded_consumed_v1_test`` (never v2 training, validation, thresholds or tuning).
3. Any member is from an *external-test publisher* (World Bank):
   * and any member is an AidData record -> ``excluded_linked_to_v1_data``;
   * otherwise -> ``external_test_candidate`` (sealed; never used for development).
4. A group with a member not permitted for training -> ``excluded_rights_training``.
5. AidData-only groups: v1 ``not_eligible`` -> ``excluded_not_eligible``; any member in v1
   primary validation -> ``validation_candidate``; else ``training_candidate``.
6. Remaining groups (IATI donors): a seeded SHA-256 bucket of the partition-group ID sends
   20 % to ``validation_candidate``, the rest to ``training_candidate``.

The partition never looks at labels, so it cannot be tuned towards scores.
"""

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

DESIGN_VERSION = "v2_partition_design_v2"
SEED = 20261109
VALIDATION_PERCENT = 20
EXTERNAL_TEST_PUBLISHERS = frozenset({"worldbank_projects"})

EXTERNAL = "external_test_candidate"
TRAIN = "training_candidate"
VALID = "validation_candidate"
CONSUMED = "excluded_consumed_v1_test"
RESTRICTED = "restricted_reference_only"
EXCL_LINKED = "excluded_linked_to_v1_data"
EXCL_NOT_ELIGIBLE = "excluded_not_eligible"
EXCL_RIGHTS_TRAINING = "excluded_rights_training"
DEVELOPMENT_PARTITIONS = frozenset({TRAIN, VALID})
ALL_PARTITIONS = frozenset(
    {
        EXTERNAL,
        TRAIN,
        VALID,
        CONSUMED,
        RESTRICTED,
        EXCL_LINKED,
        EXCL_NOT_ELIGIBLE,
        EXCL_RIGHTS_TRAINING,
    }
)


class PoolIntegrityError(RuntimeError):
    """A partition invariant (disjointness, rights, consumed-test exclusion) is violated."""


def bucket(group_id: str, seed: int = SEED) -> int:
    return int(hashlib.sha256(f"{seed}:{group_id}".encode()).hexdigest(), 16) % 100


def _role(
    group: pd.DataFrame,
    group_id: str,
    seed: int,
    restricted: frozenset[str],
    trainable: frozenset[str],
) -> tuple[str, str]:
    sources = set(group["source_id"])
    if sources & restricted:
        return RESTRICTED, f"group contains rights-restricted source {sorted(sources & restricted)}"
    if bool(group["v1_consumed_test"].fillna(False).astype(bool).any()):
        return CONSUMED, "group contains a record from a consumed v1 test partition"
    if sources & EXTERNAL_TEST_PUBLISHERS:
        if "aiddata" in sources:
            return EXCL_LINKED, "external-test publisher group linked to v1 AidData record"
        return EXTERNAL, "group contains an external-test publisher record (World Bank)"
    if not sources <= trainable:
        return EXCL_RIGHTS_TRAINING, f"not permitted for training: {sorted(sources - trainable)}"
    if sources == {"aiddata"}:
        if (group["v1_eligibility"] != "eligible").all():
            return EXCL_NOT_ELIGIBLE, "v1 eligibility_status != eligible"
        if (group["v1_primary_split"] == "validation").any():
            return VALID, "AidData group in v1 primary validation"
        return TRAIN, "AidData group in v1 primary train"
    b = bucket(group_id, seed)
    if b < VALIDATION_PERCENT:
        return VALID, f"hash bucket {b} < {VALIDATION_PERCENT}"
    return TRAIN, f"hash bucket {b} >= {VALIDATION_PERCENT}"


def assign_partitions(
    frame: pd.DataFrame,
    seed: int = SEED,
    *,
    restricted_sources: Iterable[str] = (),
    trainable_sources: Iterable[str] | None = None,
) -> pd.DataFrame:
    """``frame`` columns: candidate_id, source_id, partition_group_id, v1_consumed_test (bool),
    v1_primary_split (str|None), v1_eligibility (str|None). Returns candidate_id, v2_partition,
    v2_partition_reason, design_version.

    ``trainable_sources`` defaults to every source present that is not restricted."""
    restricted = frozenset(restricted_sources)
    trainable = (
        frozenset(trainable_sources)
        if trainable_sources is not None
        else frozenset(frame["source_id"]) - restricted
    )
    roles = {
        str(g): _role(group, str(g), seed, restricted, trainable)
        for g, group in frame.groupby("partition_group_id")
    }
    out = frame[["candidate_id", "partition_group_id"]].copy()
    out["v2_partition"] = out["partition_group_id"].map(lambda g: roles[str(g)][0])
    out["v2_partition_reason"] = out["partition_group_id"].map(lambda g: roles[str(g)][1])
    out["design_version"] = DESIGN_VERSION
    return out[["candidate_id", "v2_partition", "v2_partition_reason", "design_version"]]


def check_pool_integrity(
    membership: pd.DataFrame, restricted_sources: Iterable[str]
) -> dict[str, int]:
    """Raise ``PoolIntegrityError`` unless every invariant holds; return check counts.

    ``membership`` columns: candidate_id, source_id, project_family_id, partition_group_id,
    v2_partition, v1_consumed_test."""
    restricted = frozenset(restricted_sources)
    errors: list[str] = []
    unknown = set(membership["v2_partition"]) - ALL_PARTITIONS
    if unknown:
        errors.append(f"unknown partitions {unknown}")
    for key in ("partition_group_id", "project_family_id"):
        spread = membership.groupby(key)["v2_partition"].nunique()
        if (spread > 1).any():
            errors.append(f"{int((spread > 1).sum())} {key}s span several partitions")
    consumed = membership["v1_consumed_test"].fillna(False).astype(bool)
    in_use = membership["v2_partition"].isin(DEVELOPMENT_PARTITIONS | {EXTERNAL})
    if bool((consumed & in_use).any()):
        errors.append(f"{int((consumed & in_use).sum())} consumed v1 test records in use pools")
    misplaced = membership["source_id"].isin(restricted) & (
        membership["v2_partition"] != RESTRICTED
    )
    if bool(misplaced.any()):
        errors.append(f"{int(misplaced.sum())} restricted-source records outside {RESTRICTED}")
    dev_ext = membership["v2_partition"].isin(DEVELOPMENT_PARTITIONS) & membership[
        "source_id"
    ].isin(EXTERNAL_TEST_PUBLISHERS)
    if bool(dev_ext.any()):
        errors.append(f"{int(dev_ext.sum())} external-test publisher records in development pools")
    if errors:
        raise PoolIntegrityError("; ".join(errors))
    return {
        "records_checked": len(membership),
        "partition_groups": int(membership["partition_group_id"].nunique()),
        "project_families": int(membership["project_family_id"].nunique()),
        "consumed_v1_test_records": int(consumed.sum()),
    }


# ------------------------------------------------------------------ external-test pilot strata
PRIORITY_NON_ENERGY = frozenset(
    {
        "agriculture_forestry_fishing",
        "water_sanitation_waste",
        "transport",
        "disaster_risk_and_emergency",
        "environment_ecosystems",
        "urban_development",
        "health",
        "multisector_other",
    }
)
CONTROL_SECTORS = frozenset(
    {
        "education",
        "governance_civil_society",
        "finance",
        "social_protection_inclusion",
        "communications",
        "industry_trade_business",
    }
)
# Planning targets for a 300-record pilot. Strata use SOURCE METADATA ONLY (never a human or
# model label); they steer coverage, and inclusion probabilities are recorded for weighting.
# GCF pages are rights-restricted (ai-train=no), so the pilot uses World Bank strata only.
PILOT_TARGETS: dict[str, int] = {
    "wb_climate_theme_tagged": 50,
    "wb_priority_non_energy_untagged": 130,
    "wb_control_sector_untagged": 80,
    "wb_energy": 40,
}
PAKISTAN_SHARE = 0.30


def stratum(row: pd.Series) -> str | None:
    if row["source_id"] != "worldbank_projects":
        return None
    if row["sector_family"] == "energy":
        return "wb_energy"
    if row["wb_climate_themes"]:
        return "wb_climate_theme_tagged"
    if row["sector_family"] in PRIORITY_NON_ENERGY:
        return "wb_priority_non_energy_untagged"
    if row["sector_family"] in CONTROL_SECTORS:
        return "wb_control_sector_untagged"
    return None


def _order(candidate_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:pilot:{candidate_id}".encode()).hexdigest()


def sample_pilot(
    pool: pd.DataFrame, targets: dict[str, int] | None = None, seed: int = SEED
) -> pd.DataFrame:
    """One record per partition group, deterministic, with a Pakistan quota per stratum.

    ``pool``: external_test_candidate rows with usable text and columns source_id, gcf_theme,
    wb_climate_themes, sector_family, is_pakistan, partition_group_id, candidate_id."""
    targets = targets or PILOT_TARGETS
    pool = pool.copy()
    pool["stratum"] = [stratum(row) for _, row in pool.iterrows()]
    pool = pool[pool["stratum"].notna()]
    pool["_order"] = pool["candidate_id"].map(lambda c: _order(str(c), seed))
    # one representative per partition group (lowest hash), so related texts never co-occur
    pool = pool.sort_values("_order").drop_duplicates("partition_group_id", keep="first")
    chosen: list[pd.DataFrame] = []
    for name, target in targets.items():
        members = pool[pool["stratum"] == name].sort_values("_order")
        pk_quota = math.ceil(target * PAKISTAN_SHARE)
        pk = members[members["is_pakistan"]].head(pk_quota)
        rest = members.drop(pk.index).head(max(target - len(pk), 0))
        picked = pd.concat([pk, rest])
        picked = picked.assign(
            stratum_population=len(members), stratum_target=target, stratum_sampled=len(picked)
        )
        picked["inclusion_probability"] = len(picked) / len(members) if len(members) else 0.0
        chosen.append(picked)
    result = pd.concat(chosen, ignore_index=True) if chosen else pool.head(0)
    return (
        result.drop(columns=["_order"])
        .sort_values(["stratum", "candidate_id"])
        .reset_index(drop=True)
    )


# ------------------------------------------------------------------ sample-size policy
def wilson_half_width(p: float, n: int, z: float = 1.959964) -> float:
    if n <= 0:
        return float("nan")
    denom = 1 + z * z / n
    return (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))


def n_for_half_width(p: float, half_width: float, z: float = 1.959964) -> int:
    n = 1
    while wilson_half_width(p, n, z) > half_width:
        n += 1
    return n


@dataclass(frozen=True)
class SubgroupRequirement:
    subgroup: str
    metric: str
    assumed_rate: float
    target_half_width: float

    @property
    def minimum_n(self) -> int:
        return n_for_half_width(self.assumed_rate, self.target_half_width)


SAMPLE_SIZE_POLICY: tuple[SubgroupRequirement, ...] = (
    SubgroupRequirement("non_energy_positives", "recall", 0.75, 0.10),
    SubgroupRequirement("adaptation_only_positives", "recall", 0.70, 0.10),
    SubgroupRequirement("energy_positives", "recall", 0.85, 0.10),
    SubgroupRequirement("predicted_positives", "precision", 0.80, 0.07),
    SubgroupRequirement("negatives", "false_positive_rate", 0.10, 0.05),
    SubgroupRequirement("pakistan_positives", "recall", 0.75, 0.15),
)


def sample_size_table(observed: dict[str, int]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for req in SAMPLE_SIZE_POLICY:
        have = observed.get(req.subgroup, 0)
        rows.append(
            {
                "subgroup": req.subgroup,
                "metric": req.metric,
                "assumed_rate": req.assumed_rate,
                "target_95ci_half_width": req.target_half_width,
                "minimum_n": req.minimum_n,
                "observed_verified_n": have,
                "half_width_at_observed_n": round(wilson_half_width(req.assumed_rate, have), 3)
                if have
                else None,
                "meets_minimum": have >= req.minimum_n,
            }
        )
    return rows
