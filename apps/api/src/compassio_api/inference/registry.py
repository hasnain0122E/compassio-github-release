"""Typed view of ``configs/inference_models.yaml`` (no ML imports)."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

ModelKey = Literal["ml_v1", "ml_v2"]
Status = Literal["trusted_research_release", "development_candidate"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evaluation(_Frozen):
    kind: Literal["one_shot_frozen_test", "development_validation_used_for_selection"]
    population: str
    headline: dict[str, float]
    document: str


class ModelEntry(_Frozen):
    engine_label: str
    model_version: str
    status: Status
    loader: Literal["trusted_release", "development_candidate"]
    artifact_dir: str
    artifact_sha256: str
    model_fingerprint: str
    threshold: float
    representation: str
    training_data: str
    evaluation: Evaluation
    intended_use: str


class Demo(_Frozen):
    mode_name: Literal["authorized_local_demo"]
    default_model: ModelKey
    fallback_model: ModelKey
    allowed_environments: tuple[str, ...]
    requires_source_data_access: Literal["local_development"]


class ModelInputRights(_Frozen):
    rights_config: str
    use: Literal["automated_evaluation"]
    database_source_to_rights_source: dict[str, str]


class InferenceRegistry(_Frozen):
    version: str
    models: dict[ModelKey, ModelEntry]
    demo: Demo
    comparison_aggregates: str
    model_input_rights: ModelInputRights


def load_registry(path: Path) -> InferenceRegistry:
    return InferenceRegistry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
