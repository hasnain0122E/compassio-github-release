"""Frozen fast-track experiment plan (``configs/ml_v2_fast_experiment.yaml``)."""

import hashlib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PLAN = Path("configs") / "ml_v2_fast_experiment.yaml"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Membership(_Frozen):
    records: int
    positives: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class V1Release(_Frozen):
    release_dir: str
    model_version: str
    artifact_sha256: str
    fingerprint: str


class Inputs(_Frozen):
    audit_id: str
    build_id: str
    build_manifest_sha256: str
    development_sha256: str
    membership_sha256: str
    rights_config_sha256: str
    quality_report_sha256: str
    record_quality_sha256: str
    memberships: dict[Literal["train", "valid"], Membership]
    training_sources: tuple[str, ...]
    aiddata_augmentation: dict[str, str]
    v1_release: V1Release


class CV(_Frozen):
    n_splits: int = Field(ge=2)
    group_column: str


class Candidate(_Frozen):
    name: str
    features: str
    classifier: str
    weighting: Literal["none", "publisher_balanced", "family_inverse"]
    grid: list[dict[str, Any]] | Literal["best_of_ABC"]


class Population(_Frozen):
    train_sources: tuple[str, ...]
    valid_sources: tuple[str, ...]
    candidates: tuple[str, ...]


class Transfer(_Frozen):
    train: str
    evaluate_on: str


class Selection(_Frozen):
    population: str
    guard_min_non_energy_precision: float
    primary_metric: str
    tie_window: float
    tie_breakers: tuple[str, ...]
    improvement_claim: str
    if_no_candidate_passes_guard: str


class Bootstrap(_Frozen):
    resamples: int
    confidence: float
    group_column: str


class Slices(_Frozen):
    min_records: int
    min_positives: int
    sector_families: tuple[str, ...]


class Latency(_Frozen):
    texts: int
    repeats: int


class Artifacts(_Frozen):
    run_root: str
    model_root: str
    status: Literal["development_candidate"]


class FastPlan(_Frozen):
    plan_version: str
    seed: int
    inputs: Inputs
    label: dict[str, str]
    text_representation: Literal["title_description"]
    cv: CV
    hyperparameter_selection: Literal["train_oof_average_precision"]
    threshold: Literal["train_oof_max_f1"]
    calibration: dict[str, str]
    features: dict[str, dict[str, Any]]
    candidates: tuple[Candidate, ...]
    populations: dict[str, Population]
    transfer: tuple[Transfer, ...]
    baselines: tuple[str, ...]
    selection: Selection
    bootstrap: Bootstrap
    slices: Slices
    latency: Latency
    targets: dict[str, float]
    artifacts: Artifacts

    def candidate(self, name: str) -> Candidate:
        for cand in self.candidates:
            if cand.name == name:
                return cand
        raise KeyError(name)


class PlanError(RuntimeError):
    """The plan is missing, malformed or does not match its expected hash."""


def plan_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan(path: Path = DEFAULT_PLAN, expected_sha256: str | None = None) -> FastPlan:
    if not path.is_file():
        raise PlanError(f"plan not found: {path}")
    if expected_sha256 is not None and plan_sha256(path) != expected_sha256:
        raise PlanError(f"plan sha256 {plan_sha256(path)} != expected {expected_sha256}")
    return FastPlan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
