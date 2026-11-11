"""Typed view of ``configs/c05_poison_quarantine.yaml``."""

import hashlib
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONFIG = Path("configs") / "c05_poison_quarantine.yaml"
AttackMode = Literal["uniform", "targeted_non_energy_positive"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Cohort(_Frozen):
    plan: str
    batch_partition: Literal["train"]
    benchmark_partition: Literal["valid"]


class Attack(_Frozen):
    rate: float = Field(gt=0, lt=0.5)
    seed: int
    modes: dict[AttackMode, dict[str, Any]]


class TextModel(_Frozen):
    features: dict[str, Any]
    classifier: dict[str, Any]


class Knn(_Frozen):
    k: int = Field(ge=1, le=100)
    max_agreement: float = Field(ge=0, le=1)
    min_mean_similarity: float = Field(ge=0, le=1)


class Decision(_Frozen):
    insufficient_evidence_policy: Literal["accept_and_review", "quarantine"]


class DetectorConfig(_Frozen):
    n_splits: int = Field(ge=2, le=10)
    seed: int
    text_model: TextModel
    min_class_support: int = Field(ge=1)
    knn: Knn
    decision: Decision


class Downstream(_Frozen):
    features: Literal["word", "char", "word_char"]
    classifier: Literal["lr"]
    params: dict[str, Any]
    threshold: Literal["train_oof_max_f1"]
    n_splits: int = Field(ge=2, le=10)
    seed: int


class C05Config(_Frozen):
    config_version: str
    detector_version: str
    cohort: Cohort
    attack: Attack
    detector: DetectorConfig
    downstream: Downstream


def config_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(path: Path = DEFAULT_CONFIG) -> C05Config:
    return C05Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
