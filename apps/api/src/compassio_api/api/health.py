"""Unversioned liveness endpoint, used by local tooling and future deployment probes."""

from fastapi import APIRouter

from compassio_api import __version__
from compassio_api.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service liveness")
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="compassio-api", version=__version__)
