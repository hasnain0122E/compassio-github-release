"""Explicit local C09 adapter. Normal screening remains byte-contract compatible."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from compassio_api.api.deps import SettingsDep
from compassio_api.api.errors import error_responses
from compassio_api.api.v1.screening import ManagerDep
from compassio_api.inference.text import model_text
from compassio_api.schemas.screening import ScreeningResponse
from compassio_api.services import screening as svc

router = APIRouter(tags=["challenges"])


class GuardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=20_000)


class GuardResponse(BaseModel):
    guard_version: str
    raw: ScreeningResponse
    guarded: ScreeningResponse
    standard_api: ScreeningResponse
    requires_review: bool
    unstable_input: bool
    reasons: list[str]
    explanation_input: Literal["normalized_fields"] = "normalized_fields"
    notice: str


@router.post(
    "/challenges/c09/screen",
    response_model=GuardResponse,
    responses=error_responses(403, 422, 503),
)
def guarded_screen(body: GuardRequest, settings: SettingsDep, manager: ManagerDep) -> GuardResponse:
    if not settings.c09_enabled or not settings.ml_v2_demo_active:
        raise svc.InferenceNotAuthorizedError(
            "c09_demo_disabled", "C09 requires explicit opt-in and authorized local ML v2 mode."
        )
    # Run all existing authorization/input checks before loading or normalizing.
    # This accepts submitted text only; database screening retains its source-rights gate.
    standard = svc.screen_text(
        manager, settings, None, body.title, body.description, "ml_v2", 10, False
    )
    from compassio_ml.c09.guard import GuardedClassifier
    from compassio_ml.model_v2.artifact import ExperimentalClassifier

    loaded = manager.get("ml_v2")
    # Reuse the pipeline already loaded by the hash/fingerprint-verified manager.
    guard = GuardedClassifier(ExperimentalClassifier(loaded.pipeline, loaded.manifest))
    result = guard.predict(body.title, body.description)
    raw_title, raw_description = (body.title or "").strip(), (body.description or "").strip()
    raw = svc._response(
        loaded,
        manager,
        settings,
        raw_title,
        model_text(raw_title, raw_description),
        10,
        False,
        None,
        None,
    )
    guarded_title, guarded_description = result.normalized_fields
    guarded = svc._response(
        loaded,
        manager,
        settings,
        guarded_title,
        model_text(guarded_title, guarded_description),
        10,
        False,
        None,
        None,
    )
    return GuardResponse(
        guard_version=result.guard_version,
        raw=raw,
        guarded=guarded,
        standard_api=standard,
        requires_review=result.requires_review,
        unstable_input=result.unstable_input,
        reasons=list(result.reasons),
        notice="Live registered raw predictor and C09 adapter. The standard API separately "
        "sanitizes controls; its result is included as standard_api. "
        "Explanations describe their respective inputs; "
        "guarded offsets refer to normalized fields. Review flags do not prove an attack. "
        "Some adversarial edits still succeed. Nothing is saved.",
    )
