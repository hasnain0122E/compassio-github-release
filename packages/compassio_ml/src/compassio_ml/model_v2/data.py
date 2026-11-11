"""Development data for the fast track, loaded ONLY through the sanctioned donor loader.

Guarantees (each checked at load time, failing loudly):

* rows come from ``quality_v2.audit.load_eligible_donor_records`` (which re-runs the audit);
* TRAIN/VALID memberships equal the plan's pinned hashes and counts;
* every source is permitted for ML training and automated evaluation;
* no consumed v1 test record; no partition group, project family or identical text spans
  TRAIN and VALID;
* model inputs are text only (``title_clean`` + ``description_clean``).
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from compassio_ml.external.development import load_aiddata_development_ids
from compassio_ml.external.partition import TRAIN, VALID
from compassio_ml.external.paths import V2Paths
from compassio_ml.external.rights import Use, load_rights
from compassio_ml.integrity.hashing import sha256_file
from compassio_ml.model_v2.plan import FastPlan
from compassio_ml.modeling.features import build_texts
from compassio_ml.quality_v2.audit import load_eligible_donor_records

AIDDATA = "aiddata"


class DataIntegrityError(RuntimeError):
    """Inputs differ from the frozen plan or violate an isolation rule."""


@dataclass(frozen=True)
class DevData:
    """One row per eligible development record (TRAIN and VALID)."""

    frame: pd.DataFrame

    def part(self, name: str) -> pd.DataFrame:
        return self.frame[self.frame["part"] == name]


def membership_sha256(frame: pd.DataFrame) -> str:
    lines = sorted(frame["candidate_id"].astype(str) + "|" + frame["y"].astype(int).astype(str))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def prepare(frame: pd.DataFrame, part: str) -> pd.DataFrame:
    """Derive the label, slices and model text. Text is the ONLY model input."""
    out = pd.DataFrame(
        {
            "candidate_id": frame["candidate_id"].astype(str).to_numpy(),
            "source_id": frame["source_id"].astype(str).to_numpy(),
            "part": part,
            "text": build_texts(frame, "title_description"),
            "title": frame["title_clean"].fillna("").astype(str).to_numpy(),
            "description": frame["description_clean"].fillna("").astype(str).to_numpy(),
            "y": (frame["donor_rio_overall"].astype(float) > 0).astype(int).to_numpy(),
            "mitigation": frame["donor_rio_mitigation"].astype(float).to_numpy(),
            "adaptation": frame["donor_rio_adaptation"].astype(float).to_numpy(),
            "non_energy": (~frame["is_energy_sector"].astype(bool)).to_numpy(),
            "sector_family": frame["sector_family"].fillna("unknown").astype(str).to_numpy(),
            "group": frame["partition_group_id"].astype(str).to_numpy(),
            "family": frame["project_family_id"].astype(str).to_numpy(),
            "text_sha256": frame["text_sha256"].astype(str).to_numpy(),
            "v1_consumed_test": frame["v1_consumed_test"].astype(bool).to_numpy(),
        }
    )
    out["adaptation_only"] = (out["adaptation"] > 0) & (out["mitigation"] == 0)
    out["mitigation_only"] = (out["mitigation"] > 0) & (out["adaptation"] == 0)
    return out


def check_isolation(frame: pd.DataFrame) -> None:
    if frame["v1_consumed_test"].any():
        raise DataIntegrityError("a consumed v1 test record is present")
    for column in ("group", "family", "text_sha256"):
        spread = frame.groupby(column)["part"].nunique()
        if (spread > 1).any():
            raise DataIntegrityError(f"{column} spans TRAIN and VALID: {int((spread > 1).sum())}")


def check_rights(paths: V2Paths, sources: set[str]) -> None:
    rights = load_rights(paths.repo_root / "configs" / "ml_rights_eligibility_v2.yaml")
    for source in sorted(sources):
        if not rights.permitted(source, Use.TRAINING):
            raise DataIntegrityError(f"{source} is not permitted for ML training")
        if source != AIDDATA and not rights.permitted(source, Use.EVALUATION):
            raise DataIntegrityError(f"{source} is not permitted for automated evaluation")


def check_pins(paths: V2Paths, plan: FastPlan) -> None:
    rights_file = paths.repo_root / "configs" / "ml_rights_eligibility_v2.yaml"
    if sha256_file(rights_file) != plan.inputs.rights_config_sha256:
        raise DataIntegrityError("rights configuration changed since the plan was frozen")
    audit_dir = paths.output_root / "automated_quality" / plan.inputs.audit_id
    for name, expected in (
        ("quality_report.json", plan.inputs.quality_report_sha256),
        ("record_quality.jsonl", plan.inputs.record_quality_sha256),
    ):
        if sha256_file(audit_dir / name) != expected:
            raise DataIntegrityError(f"{name} differs from the plan pin")
    report = json.loads((audit_dir / "quality_report.json").read_text("utf-8"))
    provenance = report["inputs"]["provenance"]
    for key, expected in (
        ("build_id", plan.inputs.build_id),
        ("build_manifest_sha256", plan.inputs.build_manifest_sha256),
        ("development_sha256", plan.inputs.development_sha256),
        ("membership_sha256", plan.inputs.membership_sha256),
    ):
        if provenance.get(key) != expected:
            raise DataIntegrityError(f"audit provenance {key} differs from the plan pin")


def load_development(paths: V2Paths, plan: FastPlan) -> DevData:
    check_pins(paths, plan)
    train = prepare(load_eligible_donor_records(paths, plan.inputs.audit_id, TRAIN), "train")
    valid = prepare(load_eligible_donor_records(paths, plan.inputs.audit_id, VALID), "valid")
    pairs: tuple[tuple[Literal["train", "valid"], pd.DataFrame], ...] = (
        ("train", train),
        ("valid", valid),
    )
    for name, frame in pairs:
        pin = plan.inputs.memberships[name]
        if len(frame) != pin.records or int(frame["y"].sum()) != pin.positives:
            raise DataIntegrityError(f"{name} counts differ from the plan")
        if membership_sha256(frame) != pin.sha256:
            raise DataIntegrityError(f"{name} membership hash differs from the plan")
    frame = pd.concat([train, valid], ignore_index=True)
    check_isolation(frame)
    sources = set(frame["source_id"])
    if not sources <= set(plan.inputs.training_sources):
        raise DataIntegrityError(f"unexpected sources {sorted(sources)}")
    check_rights(paths, sources)
    return DevData(frame)


def load_aiddata_training(paths: V2Paths, plan: FastPlan) -> pd.DataFrame:
    """AidData records in the v2 TRAINING partition (never consumed v1 tests), with the
    Qi et al. 2026 label (rio_overall > 0). Used only for the augmentation ablation."""
    check_rights(paths, {AIDDATA})
    ids = load_aiddata_development_ids(paths, plan.inputs.build_id, [TRAIN])
    if paths.input_data_root is None:
        raise DataIntegrityError("COMPASSIO_DATA_ROOT is not configured")
    table_path = paths.readable(paths.input_data_root / "processed" / "research_projects.parquet")
    if sha256_file(table_path) != plan.inputs.aiddata_augmentation["research_table_sha256"]:
        raise DataIntegrityError("research table differs from the plan pin")
    table = pd.read_parquet(
        table_path,
        columns=[
            "record_id",
            "title_clean",
            "description_clean",
            "rio_overall",
            "rio_mitigation",
            "rio_adaptation",
            "sector_name",
            "eligibility_status",
        ],
    )
    merged = ids.merge(table, on="record_id", how="inner", validate="one_to_one")
    merged = merged[merged["eligibility_status"] == "eligible"]
    out = pd.DataFrame(
        {
            "candidate_id": merged["candidate_id"].astype(str).to_numpy(),
            "source_id": AIDDATA,
            "part": "train",
            "text": build_texts(merged, "title_description"),
            "y": (merged["rio_overall"].astype(int) > 0).astype(int).to_numpy(),
            "mitigation": merged["rio_mitigation"].astype(float).to_numpy(),
            "adaptation": merged["rio_adaptation"].astype(float).to_numpy(),
            "non_energy": (merged["sector_name"].astype(str) != "ENERGY").to_numpy(),
            "sector_family": "aiddata_" + merged["sector_name"].astype(str).str.lower(),
            "group": "aid:" + merged["partition_group_id"].astype(str),
            "family": "aid:" + merged["partition_group_id"].astype(str),
            "text_sha256": "",
            "v1_consumed_test": False,
        }
    )
    out["text_sha256"] = [hashlib.sha256(str(x).encode("utf-8")).hexdigest() for x in out["text"]]
    out["adaptation_only"] = (out["adaptation"] > 0) & (out["mitigation"] == 0)
    out["mitigation_only"] = (out["mitigation"] > 0) & (out["adaptation"] == 0)
    return out.reset_index(drop=True)


def cross_publisher_families(frame: pd.DataFrame) -> set[str]:
    """Project families that contain records from more than one publisher."""
    counts = frame.groupby("family")["source_id"].nunique()
    return set(counts[counts > 1].index)


def french_share(texts: np.ndarray) -> float:
    """Crude language indicator: share of texts with >= 3 common French function words."""
    markers = (" les ", " des ", " du ", " pour ", " dans ", " une ", " sur ", " et ")
    hits = [sum(m in f" {str(t).lower()} " for m in markers) >= 3 for t in texts]
    return float(np.mean(hits)) if len(hits) else 0.0


def resolve_release_dir(paths: V2Paths, release_dir: str) -> Path:
    root = paths.v1_project_root or paths.repo_root
    return (root / release_dir).resolve()
