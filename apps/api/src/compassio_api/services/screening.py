"""Screening service: model choice, input/rights checks, faithful explanations, persistence."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from compassio_api.core.config import Settings
from compassio_api.db.models import Project, Source
from compassio_api.inference.engine import LoadedModel, ModelManager, ModelUnavailableError
from compassio_api.inference.explain import METHOD
from compassio_api.inference.registry import InferenceRegistry, ModelKey
from compassio_api.inference.store import ReviewStore
from compassio_api.inference.text import SEPARATOR, input_sha256, prepare
from compassio_api.schemas.screening import (
    AdaptationOnly,
    ComparisonModel,
    ComparisonResponse,
    EvaluationOut,
    ExplanationOut,
    FeatureContribution,
    ModelChoice,
    ModelInfo,
    ModelsResponse,
    OperationalMode,
    PairedDifference,
    PredictionOut,
    ScreeningResponse,
    SourceEvidence,
    WordContribution,
)
from compassio_api.services.access import AccessPolicy

BORDERLINE = 0.10
PREDICTION_SCOPE = (
    "Climate-relevance screening of project text only. Compassio does not predict funding "
    "approval, financial return, project success, environmental impact or open funding."
)
NOT_PREDICTED = [
    "funding approval or eligibility",
    "financial return or profit",
    "environmental or climate impact",
    "whether a project is open to new funding",
]
SCORE_SEMANTICS = (
    "Model label score (agreement with climate annotations), not a probability of approval, "
    "impact or return."
)
LIMITS = {
    "ml_v1": [
        "Trained on AidData Chinese official-finance descriptions with Qi et al. 2026 labels.",
        "Reliable mainly for energy text; misses most adaptation and non-energy projects.",
        "On FCDO/EC descriptions it flags only ~29% of donor-marked climate projects.",
    ],
    "ml_v2": [
        "DEVELOPMENT CANDIDATE: not an independently validated release.",
        "Trained on FCDO + EC publisher-reported Rio markers (not human-verified).",
        "Its 2,550-record validation scores were used to select it and are optimistic.",
        "More false positives than v1 (precision 0.69 vs 0.89 on the same records).",
        "Weak evidence for transport/urban projects; never tested on unseen publishers.",
    ],
}


class InferenceNotAuthorizedError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ScreeningNotFoundError(LookupError):
    pass


class ReviewWriteDeniedError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def operational(settings: Settings, registry: InferenceRegistry) -> OperationalMode:
    writes = settings.review_api_token is not None and settings.inference_authorized
    if not settings.inference_authorized:
        return OperationalMode(
            inference_authorized=False,
            mode="inference_disabled",
            default_model=None,
            fallback_model=None,
            review_writes_enabled=False,
            notice="Model screening is local-only; no public prediction service is approved.",
        )
    if settings.ml_v2_demo_active:
        return OperationalMode(
            inference_authorized=True,
            mode="authorized_local_demo",
            default_model=registry.demo.default_model,
            fallback_model=registry.demo.fallback_model,
            review_writes_enabled=writes,
            notice="Authorized local demonstration: ML v2 (development candidate) is the "
            "default engine; ML v1 (trusted research release) is the fallback.",
        )
    return OperationalMode(
        inference_authorized=True,
        mode="standard_local_research",
        default_model="ml_v1",
        fallback_model=None,
        review_writes_enabled=writes,
        notice="ML v1 trusted research release only (ML v2 demo mode not enabled).",
    )


def model_info(manager: ModelManager, settings: Settings, key: ModelKey) -> ModelInfo:
    entry = manager.registry.models[key]
    selectable = settings.inference_authorized and (key == "ml_v1" or settings.ml_v2_demo_active)
    return ModelInfo(
        model_key=key,
        engine_label=entry.engine_label,
        model_version=entry.model_version,
        status=entry.status,
        artifact_sha256=entry.artifact_sha256,
        model_fingerprint=entry.model_fingerprint,
        threshold=entry.threshold,
        representation=entry.representation,
        training_data=entry.training_data,
        intended_use=entry.intended_use,
        evaluation=EvaluationOut(
            **entry.evaluation.model_dump(),
            independent_generalization_evidence=entry.evaluation.kind == "one_shot_frozen_test",
        ),
        artifact_present=manager.artifact_present(key),
        selectable_now=selectable,
    )


def list_models(manager: ModelManager, settings: Settings) -> ModelsResponse:
    keys: tuple[ModelKey, ...] = ("ml_v2", "ml_v1")
    return ModelsResponse(
        models=[model_info(manager, settings, k) for k in keys],
        operational=operational(settings, manager.registry),
        prediction_scope=PREDICTION_SCOPE,
    )


def choose_model(
    settings: Settings, registry: InferenceRegistry, requested: ModelChoice
) -> ModelKey:
    if not settings.inference_authorized:
        raise InferenceNotAuthorizedError(
            "inference_not_authorized",
            "Model screening is available only in local development mode; no public "
            "prediction service is approved.",
        )
    if requested == "ml_v2" and not settings.ml_v2_demo_active:
        raise InferenceNotAuthorizedError(
            "ml_v2_demo_not_authorized",
            "ML v2 is a development candidate, usable only in the authorized local demo "
            "(COMPASSIO_ML_V2_LOCAL_DEMO=true, environment=development).",
        )
    if requested == "default":
        return registry.demo.default_model if settings.ml_v2_demo_active else "ml_v1"
    return requested


def _get(
    manager: ModelManager, settings: Settings, key: ModelKey, requested: ModelChoice
) -> tuple[LoadedModel, bool]:
    """Load ``key``; for the DEFAULT choice in demo mode, fall back to v1 if v2 is unusable."""
    try:
        return manager.get(key), False
    except ModelUnavailableError:
        fallback = manager.registry.demo.fallback_model
        if requested == "default" and settings.ml_v2_demo_active and key != fallback:
            return manager.get(fallback), True
        raise


def _band(
    score: float, threshold: float
) -> Literal["clearly_flagged", "borderline", "not_flagged"]:
    if abs(score - threshold) <= BORDERLINE:
        return "borderline"
    return "clearly_flagged" if score >= threshold else "not_flagged"


FieldName = Literal["title", "description", "unknown"]


def _field(start: int, title: str) -> tuple[FieldName, int]:
    if start < 0:
        return "unknown", -1
    if start < len(title):
        return "title", start
    offset = len(title) + len(SEPARATOR) if title else 0
    return "description", start - offset


def _response(
    loaded: LoadedModel,
    manager: ModelManager,
    settings: Settings,
    title: str,
    text: str,
    top_k: int,
    fallback_used: bool,
    evidence: SourceEvidence | None,
    screening_id: str | None,
) -> ScreeningResponse:
    exp = loaded.score_and_explain(text, top_k)
    words = []
    for span, value in exp.word_attributions[: top_k * 2]:
        field, start = _field(span.start, title)
        end = start + (span.end - span.start) if start >= 0 else -1
        words.append(
            WordContribution(
                word=span.word,
                field=field,
                start=start,
                end=end,
                contribution=value,
            )
        )
    threshold = loaded.entry.threshold
    guidance = [
        "Screening aid only: a person must review every flagged and unflagged record.",
        "Check the highlighted words against the full description before deciding.",
    ]
    if _band(exp.score, threshold) == "borderline":
        guidance.insert(0, "Borderline score: treat as uncertain and review carefully.")
    mode: Literal["authorized_local_demo", "standard_local_research"] = (
        "authorized_local_demo" if settings.ml_v2_demo_active else "standard_local_research"
    )
    return ScreeningResponse(
        screening_id=screening_id,
        saved=screening_id is not None,
        model=model_info(manager, settings, loaded.key),
        operational_mode=mode,
        fallback_used=fallback_used,
        prediction=PredictionOut(
            is_climate_related=exp.score >= threshold,
            label_score=exp.score,
            threshold=threshold,
            band=_band(exp.score, threshold),
            score_semantics=SCORE_SEMANTICS,
        ),
        explanation=ExplanationOut(
            method=METHOD,
            intercept=exp.intercept,
            logit=exp.logit,
            faithfulness_abs_error=exp.faithfulness_abs_error,
            nonzero_features=exp.nonzero_features,
            feature_contribution_total=exp.feature_contribution_total,
            word_contribution_total=exp.word_contribution_total,
            top_positive_features=[
                FeatureContribution(feature=f, contribution=c) for f, c in exp.positive_features
            ],
            top_negative_features=[
                FeatureContribution(feature=f, contribution=c) for f, c in exp.negative_features
            ],
            word_attribution_available=exp.word_attribution_available,
            top_words=words,
        ),
        input_sha256=input_sha256(text),
        source_evidence=evidence,
        guidance=guidance,
        limitations=LIMITS[loaded.key],
        not_predicted=NOT_PREDICTED,
        generated_at=datetime.now(UTC),
    )


def screen_text(
    manager: ModelManager,
    settings: Settings,
    store: ReviewStore | None,
    title: str | None,
    description: str | None,
    requested: ModelChoice,
    top_k: int,
    save: bool,
) -> ScreeningResponse:
    key = choose_model(settings, manager.registry, requested)
    t, d, text = prepare(title, description)
    loaded, fallback = _get(manager, settings, key, requested)
    screening_id = None
    if save:
        assert store is not None
        exp = loaded.score_and_explain(text, 1)
        screening_id = _persist(store, loaded, settings, exp.score, text, None, None, t, d)
    return _response(loaded, manager, settings, t, text, top_k, fallback, None, screening_id)


class SourceNotPermittedError(Exception):
    def __init__(self, source_id: str) -> None:
        super().__init__(source_id)
        self.message = (
            f"Records from '{source_id}' are not permitted as model input (automated_evaluation "
            "is not permitted for this source in configs/ml_rights_eligibility_v2.yaml)."
        )


def model_input_permission(registry: InferenceRegistry, root: Path, source_id: str) -> str:
    from compassio_ml.external.rights import Use, load_rights

    rights_key = registry.model_input_rights.database_source_to_rights_source.get(source_id)
    if rights_key is None:
        raise SourceNotPermittedError(source_id)
    rights = load_rights(root / registry.model_input_rights.rights_config)
    if not rights.permitted(rights_key, Use.EVALUATION):
        raise SourceNotPermittedError(source_id)
    return f"{rights_key}: automated_evaluation {rights.status(rights_key, Use.EVALUATION)}"


def screen_project(
    session: Session,
    policy: AccessPolicy,
    manager: ModelManager,
    settings: Settings,
    store: ReviewStore | None,
    project_id: str,
    requested: ModelChoice,
    top_k: int,
    save: bool,
) -> ScreeningResponse:
    from compassio_api.services.projects import ProjectNotFoundError

    key = choose_model(settings, manager.registry, requested)
    project = session.get(Project, project_id)
    if project is None or not policy.allows(project.source_id):
        raise ProjectNotFoundError(project_id)
    permission = model_input_permission(
        manager.registry, Path(settings.inference_root), project.source_id
    )
    t, d, text = prepare(project.title, project.description)
    source = session.get_one(Source, project.source_id)
    evidence = SourceEvidence(
        project_id=project.id,
        source_id=project.source_id,
        source_reference=project.source_reference,
        title=t,
        description=d or None,
        rights_status=source.rights_status,
        model_input_permission=permission,
    )
    loaded, fallback = _get(manager, settings, key, requested)
    screening_id = None
    if save:
        assert store is not None
        exp = loaded.score_and_explain(text, 1)
        screening_id = _persist(
            store, loaded, settings, exp.score, text, project.id, project.source_id, None, None
        )
    return _response(loaded, manager, settings, t, text, top_k, fallback, evidence, screening_id)


def _persist(
    store: ReviewStore,
    loaded: LoadedModel,
    settings: Settings,
    score: float,
    text: str,
    project_id: str | None,
    source_id: str | None,
    title: str | None,
    description: str | None,
) -> str:
    record = store.save_screening(
        model_key=loaded.key,
        model_version=loaded.entry.model_version,
        model_status=loaded.entry.status,
        operational_mode="authorized_local_demo"
        if settings.ml_v2_demo_active
        else "standard_local_research",
        artifact_sha256=loaded.entry.artifact_sha256,
        model_fingerprint=loaded.entry.model_fingerprint,
        threshold=loaded.entry.threshold,
        score=score,
        is_climate_related=score >= loaded.entry.threshold,
        input_sha256=input_sha256(text),
        project_id=project_id,
        source_id=source_id,
        saved_title=title,
        saved_description=description,
    )
    return record.screening_id


def comparison(manager: ModelManager, root: Path) -> ComparisonResponse:
    data: dict[str, Any] = json.loads(
        (root / manager.registry.comparison_aggregates).read_text("utf-8")
    )

    def block(name: str, key: ModelKey) -> ComparisonModel:
        raw, entry = data[name], manager.registry.models[key]
        return ComparisonModel(
            label=entry.engine_label,
            model_version=entry.model_version,
            status=entry.status,
            threshold=raw["threshold"],
            metrics=raw["metrics"],
            intervals_95=raw["intervals_95"],
            confusion=raw["confusion"],
            predicted_positive=raw["predicted_positive"],
            adaptation_only=AdaptationOnly(**raw["adaptation_only"]),
            publisher=raw["publisher"],
        )

    v1, v2 = block("ml_v1", "ml_v1"), block("ml_v2", "ml_v2")
    pop = data["population"]
    return ComparisonResponse(
        population_description=pop["description"],
        records=pop["records"],
        positives=pop["positives"],
        by_publisher=pop["by_publisher"],
        used_for_model_selection=pop["used_for_model_selection"],
        ml_v1=v1,
        ml_v2=v2,
        paired_differences_ml_v2_minus_ml_v1={
            k: PairedDifference(**v)
            for k, v in data["paired_differences_ml_v2_minus_ml_v1"].items()
        },
        false_positive_tradeoff={
            "ml_v1_false_positives": v1.confusion["fp"],
            "ml_v2_false_positives": v2.confusion["fp"],
            "additional_false_positives": v2.confusion["fp"] - v1.confusion["fp"],
            "additional_true_positives": v2.confusion["tp"] - v1.confusion["tp"],
        },
        caveats=data["caveats"],
        source_run_id=data["run_id"],
        source_plan_sha256=data["plan_sha256"],
        source_files_sha256=data["source_files_sha256"],
    )
