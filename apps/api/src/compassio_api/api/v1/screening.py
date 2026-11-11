"""Model metadata, v1/v2 comparison, screening and review routes (Task 007).

Screening is local-only (403 ``inference_not_authorized`` otherwise); ML v2 additionally needs
the authorized local demo mode. Persisting anything needs the review token.
"""

import hmac
from datetime import UTC
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi import Path as PathParam

from compassio_api.api.deps import DataPolicyDep, SessionDep, SettingsDep
from compassio_api.api.errors import error_responses
from compassio_api.core.config import Settings
from compassio_api.inference.engine import ModelManager
from compassio_api.inference.registry import load_registry
from compassio_api.inference.store import ReviewDecision, ReviewStore
from compassio_api.schemas.screening import (
    ComparisonResponse,
    ModelsResponse,
    ProjectScreeningRequest,
    ReviewListResponse,
    ReviewOut,
    ReviewRequest,
    ScreeningResponse,
    TextScreeningRequest,
)
from compassio_api.services import screening as svc

router = APIRouter(tags=["screening"])


def build_model_manager(settings: Settings) -> ModelManager:
    """Lazily-loading manager: imports no ML code until a model is requested."""
    root = Path(settings.inference_root)
    return ModelManager(
        load_registry(root / settings.inference_registry_path),
        root,
        root / settings.trusted_registry_path,
    )


def get_manager(request: Request, settings: SettingsDep) -> ModelManager:
    manager: ModelManager | None = getattr(request.app.state, "model_manager", None)
    if manager is None:
        manager = build_model_manager(settings)
        request.app.state.model_manager = manager
    return manager


ManagerDep = Annotated[ModelManager, Depends(get_manager)]


def _store(request: Request, settings: Settings) -> ReviewStore:
    store: ReviewStore | None = getattr(request.app.state, "review_store", None)
    if store is None:
        store = ReviewStore(settings.review_database_url)
        request.app.state.review_store = store
    return store


def require_writer(
    request: Request,
    settings: SettingsDep,
    token: Annotated[str | None, Header(alias="X-Compassio-Review-Token")] = None,
) -> ReviewStore:
    if not settings.inference_authorized or settings.review_api_token is None:
        raise svc.ReviewWriteDeniedError(
            403, "review_writes_disabled", "Saving screenings and recording reviews is disabled."
        )
    expected = settings.review_api_token.get_secret_value().encode()
    if token is None or not hmac.compare_digest(token.encode(), expected):
        raise svc.ReviewWriteDeniedError(
            401, "invalid_review_token", "A valid X-Compassio-Review-Token header is required."
        )
    return _store(request, settings)


WriterDep = Annotated[ReviewStore, Depends(require_writer)]


def optional_writer(
    request: Request,
    settings: SettingsDep,
    body_save: bool,
    token: str | None,
) -> ReviewStore | None:
    return require_writer(request, settings, token) if body_save else None


@router.get(
    "/models",
    response_model=ModelsResponse,
    summary="Available models, statuses, provenance and the operational mode",
)
def models(manager: ManagerDep, settings: SettingsDep) -> ModelsResponse:
    return svc.list_models(manager, settings)


@router.get(
    "/models/comparison",
    response_model=ComparisonResponse,
    summary="Fixed v1 vs v2 aggregates on the same 2,550 development-validation records",
)
def comparison(manager: ManagerDep, settings: SettingsDep) -> ComparisonResponse:
    return svc.comparison(manager, Path(settings.inference_root))


@router.post(
    "/screening/text",
    response_model=ScreeningResponse,
    summary="Screen submitted title/description text (not stored unless save=true)",
    responses=error_responses(401, 403, 422, 503),
)
def screen_text(
    body: TextScreeningRequest,
    request: Request,
    manager: ManagerDep,
    settings: SettingsDep,
    token: Annotated[str | None, Header(alias="X-Compassio-Review-Token")] = None,
) -> ScreeningResponse:
    store = optional_writer(request, settings, body.save, token)
    return svc.screen_text(
        manager, settings, store, body.title, body.description, body.model, body.top_k, body.save
    )


@router.post(
    "/screening/projects/{project_id}",
    response_model=ScreeningResponse,
    summary="Screen an eligible database project record (source rights checked)",
    responses=error_responses(401, 403, 404, 422, 503),
)
def screen_project(
    body: ProjectScreeningRequest,
    request: Request,
    session: SessionDep,
    policy: DataPolicyDep,
    manager: ManagerDep,
    settings: SettingsDep,
    project_id: Annotated[str, PathParam(min_length=3, max_length=240)],
    token: Annotated[str | None, Header(alias="X-Compassio-Review-Token")] = None,
) -> ScreeningResponse:
    store = optional_writer(request, settings, body.save, token)
    return svc.screen_project(
        session, policy, manager, settings, store, project_id, body.model, body.top_k, body.save
    )


def _review_out(row: ReviewDecision) -> ReviewOut:
    return ReviewOut(
        review_id=row.id,
        screening_id=row.screening_id,
        decision=row.decision,  # type: ignore[arg-type]
        reviewer=row.reviewer,
        note=row.note,
        created_at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC),
        prev_hash=row.prev_hash,
        row_hash=row.row_hash,
    )


@router.post(
    "/reviews",
    response_model=ReviewOut,
    status_code=201,
    summary="Record a user-initiated review decision (append-only, hash-chained)",
    responses=error_responses(401, 403, 404, 422),
)
def add_review(body: ReviewRequest, store: WriterDep) -> ReviewOut:
    if store.get_screening(body.screening_id) is None:
        raise svc.ScreeningNotFoundError(body.screening_id)
    return _review_out(store.add_review(body.screening_id, body.decision, body.note, body.reviewer))


@router.get(
    "/reviews/{screening_id}",
    response_model=ReviewListResponse,
    summary="Review decisions for a saved screening, with audit-chain verification",
    responses=error_responses(401, 403, 404),
)
def list_reviews(
    store: WriterDep, screening_id: Annotated[str, PathParam(min_length=36, max_length=36)]
) -> ReviewListResponse:
    if store.get_screening(screening_id) is None:
        raise svc.ScreeningNotFoundError(screening_id)
    chain = store.verify_chain()
    return ReviewListResponse(
        screening_id=screening_id,
        reviews=[_review_out(r) for r in store.reviews_for(screening_id)],
        chain_valid=chain.valid,
        chain_length=chain.decisions,
    )
