"""Version 1 of the API, mounted under ``/api/v1``."""

from fastapi import APIRouter

from compassio_api.api.v1 import catalog, challenges, decision, discovery, meta, projects, screening

router = APIRouter()
router.include_router(meta.router)
router.include_router(catalog.router)
router.include_router(projects.router)
router.include_router(discovery.router)
router.include_router(screening.router)
router.include_router(decision.router)
router.include_router(challenges.router)

# Task 007: model screening (local-only; ML v2 only in the authorized local demo).

__all__ = ["router"]
