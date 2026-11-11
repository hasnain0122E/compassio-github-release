"""Schemas for model metadata, the v1/v2 comparison, screening, explanations and reviews."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ModelChoice = Literal["default", "ml_v1", "ml_v2"]
Decision = Literal["agree", "disagree", "uncertain"]


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True, protected_namespaces=())


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class EvaluationOut(_Out):
    kind: Literal["one_shot_frozen_test", "development_validation_used_for_selection"]
    population: str
    headline: dict[str, float]
    document: str
    independent_generalization_evidence: bool


class ModelInfo(_Out):
    model_key: Literal["ml_v1", "ml_v2"]
    engine_label: str
    model_version: str
    status: Literal["trusted_research_release", "development_candidate"]
    artifact_sha256: str
    model_fingerprint: str
    threshold: float
    representation: str
    training_data: str
    intended_use: str
    evaluation: EvaluationOut
    artifact_present: bool
    selectable_now: bool


class OperationalMode(_Out):
    inference_authorized: bool
    mode: Literal["authorized_local_demo", "standard_local_research", "inference_disabled"]
    default_model: Literal["ml_v1", "ml_v2"] | None
    fallback_model: Literal["ml_v1", "ml_v2"] | None
    review_writes_enabled: bool
    notice: str


class ModelsResponse(_Out):
    models: list[ModelInfo]
    operational: OperationalMode
    prediction_scope: str


class PairedDifference(_Out):
    difference: float
    low: float | None
    high: float | None
    valid_resamples: int


class AdaptationOnly(_Out):
    positives: int
    detected: int
    recall: float | None


class ComparisonModel(_Out):
    label: str
    model_version: str
    status: Literal["trusted_research_release", "development_candidate"]
    threshold: float
    metrics: dict[str, float | None]
    intervals_95: dict[str, list[float | None]]
    confusion: dict[str, int]
    predicted_positive: int
    adaptation_only: AdaptationOnly
    publisher: dict[str, dict[str, float | int | None]]


class ComparisonResponse(_Out):
    population_description: str
    records: int
    positives: int
    by_publisher: dict[str, dict[str, int]]
    used_for_model_selection: bool
    ml_v1: ComparisonModel
    ml_v2: ComparisonModel
    paired_differences_ml_v2_minus_ml_v1: dict[str, PairedDifference]
    false_positive_tradeoff: dict[str, int]
    caveats: list[str]
    source_run_id: str
    source_plan_sha256: str
    source_files_sha256: dict[str, str]


class TextScreeningRequest(_In):
    title: str | None = Field(default=None, max_length=1_000)
    description: str | None = Field(default=None, max_length=20_000)
    model: ModelChoice = "default"
    top_k: int = Field(default=10, ge=1, le=25)
    save: bool = Field(default=False, description="Persist the text (needs the review token)")


class ProjectScreeningRequest(_In):
    model: ModelChoice = "default"
    top_k: int = Field(default=10, ge=1, le=25)
    save: bool = False


class FeatureContribution(_Out):
    feature: str
    contribution: float


class WordContribution(_Out):
    word: str
    field: Literal["title", "description", "unknown"]
    start: int = Field(description="Character offset within the field; -1 if unavailable")
    end: int
    contribution: float


class ExplanationOut(_Out):
    method: str
    intercept: float
    logit: float
    faithfulness_abs_error: float
    nonzero_features: int
    feature_contribution_total: float = Field(
        description="Sum over ALL non-zero features; intercept + total = logit"
    )
    word_contribution_total: float | None = Field(
        description="Sum over ALL word attributions; equals the feature total when available"
    )
    top_positive_features: list[FeatureContribution]
    top_negative_features: list[FeatureContribution]
    word_attribution_available: bool
    top_words: list[WordContribution]


class PredictionOut(_Out):
    is_climate_related: bool
    label_score: float
    threshold: float
    band: Literal["clearly_flagged", "borderline", "not_flagged"]
    score_semantics: str


class SourceEvidence(_Out):
    project_id: str
    source_id: str
    source_reference: str
    title: str
    description: str | None
    rights_status: str
    model_input_permission: str


class ScreeningResponse(_Out):
    screening_id: str | None
    saved: bool
    model: ModelInfo
    operational_mode: Literal["authorized_local_demo", "standard_local_research"]
    fallback_used: bool
    prediction: PredictionOut
    explanation: ExplanationOut
    input_sha256: str
    source_evidence: SourceEvidence | None = None
    guidance: list[str]
    limitations: list[str]
    not_predicted: list[str]
    generated_at: datetime


class ReviewRequest(_In):
    screening_id: str = Field(min_length=36, max_length=36)
    decision: Decision
    reviewer: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2_000)


class ReviewOut(_Out):
    review_id: int
    screening_id: str
    decision: Decision
    reviewer: str
    note: str | None
    created_at: datetime
    prev_hash: str
    row_hash: str


class ReviewListResponse(_Out):
    screening_id: str
    reviews: list[ReviewOut]
    chain_valid: bool
    chain_length: int
