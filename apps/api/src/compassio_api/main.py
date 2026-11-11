"""FastAPI application factory.

The ASGI application is ``compassio_api.main:app`` (package ``compassio_api`` installed from
``apps/api/src`` by the uv workspace). Run from the repository root::

    uv run uvicorn compassio_api.main:app --host 127.0.0.1 --port 8000

(``apps.api.main:app`` is NOT an import path: ``apps/api`` is not a Python package.)
Run ONE worker process: the screening rate limiter and the review-store write lock are
in-process (docs/hackathon/local_demo_runbook.md).
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from compassio_api import __version__
from compassio_api.api import health, v1
from compassio_api.api.errors import install_error_handlers
from compassio_api.core.availability import Admission, AvailabilityShield, Budget
from compassio_api.core.config import (
    API_V1_PREFIX,
    PRODUCT_NAME,
    PRODUCT_TAGLINE,
    Settings,
    get_settings,
)
from compassio_api.core.middleware import (
    BodySizeLimit,
    EventLoopbackGuard,
    ScreeningRateLimit,
    SecurityHeaders,
)
from compassio_api.db.session import create_read_engine, session_factory
from compassio_api.inference.registry import ModelKey
from compassio_api.services.event_access import load_event_authorization

ACCESS_HEADER = "X-Compassio-Data-Access"
logger = logging.getLogger("compassio_api")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API application. Pass ``settings`` to override environment configuration."""
    resolved = settings if settings is not None else get_settings()
    access_mode = resolved.effective_source_access
    engine = create_read_engine(resolved.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if resolved.preload_models and resolved.inference_authorized:
            from compassio_api.api.v1.screening import build_model_manager
            from compassio_api.inference.engine import ModelUnavailableError

            manager = build_model_manager(resolved)
            keys: list[ModelKey] = ["ml_v1", "ml_v2"] if resolved.ml_v2_demo_active else ["ml_v1"]
            for key in keys:
                # Verifies the pinned SHA-256/fingerprint. A failure does not stop the data API;
                # screening with that model then returns 503 model_unavailable.
                try:
                    manager.get(key)
                    logger.info("preloaded and verified model %s", key)
                except ModelUnavailableError as exc:
                    logger.error("model %s unavailable at startup: %s", key, exc.message)
            app.state.model_manager = manager
        yield
        store = getattr(app.state, "review_store", None)
        if store is not None:
            store.engine.dispose()
        engine.dispose()

    app = FastAPI(
        title=f"{PRODUCT_NAME} API",
        description=PRODUCT_TAGLINE,
        version=__version__,
        lifespan=lifespan,
        docs_url=None if resolved.environment == "production" else "/docs",
        redoc_url=None if resolved.environment == "production" else "/redoc",
        openapi_url=None if resolved.environment == "production" else "/openapi.json",
    )
    app.dependency_overrides[get_settings] = lambda: resolved
    # Read-only engine; connects lazily on first query, so /health works without a database.
    app.state.session_factory = session_factory(engine)
    app.state.event_authorization = None
    if access_mode == "hackathon_event":
        assert resolved.event_authorization is not None  # enforced by Settings
        # Fails loudly at startup when the named authorization is missing or invalid.
        app.state.event_authorization = load_event_authorization(
            Path(resolved.event_authorizations_path), resolved.event_authorization
        )
    install_error_handlers(app)

    async def _internal_error(_: Request, exc: Exception) -> JSONResponse:
        # No stack trace, exception text or request content in the response.
        logger.error("unhandled %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": "Internal server error."},
        )

    app.add_exception_handler(Exception, _internal_error)

    @app.middleware("http")
    async def _access_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(API_V1_PREFIX):
            response.headers[ACCESS_HEADER] = access_mode
        return response

    if resolved.c11_enabled:
        limiter = Admission(
            {
                "screen": (
                    Budget(resolved.c11_screen_rate, resolved.c11_screen_burst),
                    Budget(resolved.c11_global_screen_rate, resolved.c11_global_screen_burst),
                ),
                "read": (
                    Budget(resolved.c11_read_rate, resolved.c11_read_burst),
                    Budget(resolved.c11_global_read_rate, resolved.c11_global_read_burst),
                ),
            },
            max_keys=resolved.c11_max_keys,
            idle_seconds=resolved.c11_idle_seconds,
        )
        app.state.c11_limiter = limiter
        app.add_middleware(AvailabilityShield, limiter=limiter)
    elif resolved.screening_rate_limit_per_minute > 0:
        app.add_middleware(
            ScreeningRateLimit,
            per_minute=resolved.screening_rate_limit_per_minute,
            prefix=f"{API_V1_PREFIX}/screening/",
        )
    if access_mode == "hackathon_event":
        app.add_middleware(EventLoopbackGuard, prefix=API_V1_PREFIX)
    app.add_middleware(BodySizeLimit, max_bytes=resolved.max_request_body_bytes)
    app.add_middleware(SecurityHeaders, api_prefix=API_V1_PREFIX)
    # CORS is added LAST so it is the outermost layer: early 413/429/403 responses from the
    # hardening middleware still carry CORS headers (readable by the browser frontend), and
    # preflight OPTIONS requests are answered before any limiter sees them.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Compassio-Review-Token"],
        expose_headers=["Retry-After"],
    )
    app.include_router(health.router)
    app.include_router(v1.router, prefix=API_V1_PREFIX)
    return app


app = create_app()
