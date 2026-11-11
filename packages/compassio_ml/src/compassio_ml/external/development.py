"""The only sanctioned loader of v2 development data (training + validation).

Future training, threshold-selection, calibration and tuning code must obtain data through
:func:`load_development_pool` / :func:`load_aiddata_development_ids`. They:

* read only ``datasets/<build_id>/`` (never ``sealed_external_test/``,
  ``restricted_reference/`` or ``labeling/``);
* refuse any partition other than ``training_candidate`` / ``validation_candidate``;
* re-check that no external-test publisher, rights-restricted source or consumed v1 test
  record is present, and raise if one is.
"""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from compassio_ml.external.partition import (
    DEVELOPMENT_PARTITIONS,
    EXTERNAL_TEST_PUBLISHERS,
    PoolIntegrityError,
)
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.rights import Use, load_rights


class ForbiddenPoolError(PermissionError):
    """A development loader was asked for sealed, restricted or excluded data."""


def _development_dir(paths: V2Paths, build_id: str) -> Path:
    directory = (paths.datasets / build_id).resolve()
    if directory.parent != paths.datasets.resolve():
        raise ForbiddenPoolError(f"{directory} is not a direct development dataset directory")
    for forbidden in (paths.sealed, paths.restricted_reference, paths.labeling):
        if forbidden.resolve() in directory.parents or directory == forbidden.resolve():
            raise ForbiddenPoolError(f"{directory} is not a development dataset directory")
    if not (directory / "build_manifest.json").is_file():
        raise FileNotFoundError(f"No v2 build at {directory}")
    return directory


def _check_partitions(partitions: Iterable[str]) -> frozenset[str]:
    requested = frozenset(partitions)
    if not requested or not requested <= DEVELOPMENT_PARTITIONS:
        raise ForbiddenPoolError(
            f"Development code may only load {sorted(DEVELOPMENT_PARTITIONS)}; "
            f"requested {sorted(requested)}"
        )
    return requested


def load_development_pool(
    paths: V2Paths,
    build_id: str,
    partitions: Iterable[str] = DEVELOPMENT_PARTITIONS,
    rights_path: Path | None = None,
) -> pd.DataFrame:
    """External (IATI) development records of one build, re-validated on load."""
    requested = _check_partitions(partitions)
    directory = _development_dir(paths, build_id)
    frame = pd.read_parquet(directory / "candidates.parquet")
    rights = load_rights(
        rights_path or paths.repo_root / "configs" / "ml_rights_eligibility_v2.yaml"
    )
    problems: list[str] = []
    if not set(frame["v2_partition"]) <= DEVELOPMENT_PARTITIONS:
        problems.append(f"non-development partitions {set(frame['v2_partition'])}")
    if frame["source_id"].isin(EXTERNAL_TEST_PUBLISHERS).any():
        problems.append("external-test publisher records present")
    untrainable = {s for s in set(frame["source_id"]) if not rights.permitted(s, Use.TRAINING)}
    if untrainable:
        problems.append(f"sources not permitted for training: {sorted(untrainable)}")
    if frame["v1_consumed_test"].fillna(False).astype(bool).any():
        problems.append("consumed v1 test records present")
    if problems:
        raise PoolIntegrityError(f"{directory / 'candidates.parquet'}: {'; '.join(problems)}")
    return frame[frame["v2_partition"].isin(requested)].reset_index(drop=True)


def load_aiddata_development_ids(
    paths: V2Paths,
    build_id: str,
    partitions: Iterable[str] = DEVELOPMENT_PARTITIONS,
    rights_path: Path | None = None,
) -> pd.DataFrame:
    """AidData record IDs (no text) with their v2 development role; consumed v1 tests never
    appear because their partition is ``excluded_consumed_v1_test``."""
    requested = _check_partitions(partitions)
    directory = _development_dir(paths, build_id)
    rights = load_rights(
        rights_path or paths.repo_root / "configs" / "ml_rights_eligibility_v2.yaml"
    )
    if not rights.permitted("aiddata", Use.TRAINING):
        raise PoolIntegrityError("AidData is not permitted for training under current rights")
    membership = pd.read_parquet(directory / "partition_membership.parquet")
    aid = membership[
        (membership["source_id"] == "aiddata") & membership["v2_partition"].isin(requested)
    ]
    if aid["v1_consumed_test"].astype(bool).any():
        raise PoolIntegrityError("consumed v1 test record in an AidData development pool")
    out = aid[["candidate_id", "v2_partition", "partition_group_id"]].copy()
    out["record_id"] = out["candidate_id"].str.removeprefix("aiddata:")
    return out.reset_index(drop=True)
