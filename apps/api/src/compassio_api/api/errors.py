"""Explicit JSON error responses ({"code", "message"}) for domain exceptions."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from compassio_api.db.session import DatabaseNotReadyError
from compassio_api.schemas.data import ErrorResponse
from compassio_api.services.access import SourceRightsNotClearedError
from compassio_api.services.finance import UnknownMetricError
from compassio_api.services.projects import ProjectNotFoundError


class InvalidQueryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _json(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorResponse(code=code, message=message).model_dump()
    )


def error_responses(*statuses: int) -> dict[int | str, dict[str, object]]:
    return {status: {"model": ErrorResponse} for status in statuses}


def install_error_handlers(app: FastAPI) -> None:
    async def rights(_: Request, exc: Exception) -> JSONResponse:
        message = exc.message if isinstance(exc, SourceRightsNotClearedError) else str(exc)
        return _json(403, "source_rights_not_cleared", message)

    async def not_found(_: Request, exc: Exception) -> JSONResponse:
        return _json(404, "project_not_found", f"No project with id {exc!s}")

    async def unknown_metric(_: Request, exc: Exception) -> JSONResponse:
        return _json(
            404, "unknown_metric", f"Unknown metric {exc!s}; see /api/v1/analytics/metrics"
        )

    async def invalid(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, InvalidQueryError):
            return _json(422, exc.code, exc.message)
        return _json(422, "invalid_query", str(exc))

    async def not_ready(_: Request, _exc: Exception) -> JSONResponse:
        return _json(
            503,
            "database_not_ready",
            "The project database is missing or not migrated. Run `uv run compassio-db migrate` "
            "and `uv run compassio-db ingest --source all`.",
        )

    from compassio_api.inference.engine import ModelUnavailableError
    from compassio_api.inference.text import InvalidInputError
    from compassio_api.services.screening import (
        InferenceNotAuthorizedError,
        ReviewWriteDeniedError,
        ScreeningNotFoundError,
        SourceNotPermittedError,
    )

    async def not_authorized(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, InferenceNotAuthorizedError)
        return _json(403, exc.code, exc.message)

    async def bad_text(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, InvalidInputError)
        return _json(422, exc.code, exc.message)

    async def unavailable(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ModelUnavailableError)
        return _json(503, "model_unavailable", f"{exc.key}: {exc.message}")

    async def source_denied(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, SourceNotPermittedError)
        return _json(403, "source_not_permitted_for_model_input", exc.message)

    async def screening_missing(_: Request, exc: Exception) -> JSONResponse:
        return _json(404, "screening_not_found", f"No saved screening {exc!s}")

    async def write_denied(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ReviewWriteDeniedError)
        return _json(exc.status, exc.code, exc.message)

    from compassio_api.services.decision.errors import DecisionInputError

    async def decision_input(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, DecisionInputError)
        return _json(422, exc.code, exc.message)

    async def validation(_: Request, exc: Exception) -> JSONResponse:
        # Same {code, message} envelope as every other error, plus FastAPI's `detail` list
        # (loc/msg/type only: submitted values are never echoed back).
        assert isinstance(exc, RequestValidationError)
        detail = [
            {"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "")), "type": e.get("type")}
            for e in exc.errors()
        ]
        first = detail[0] if detail else {"loc": [], "msg": "invalid request"}
        where = ".".join(str(part) for part in first["loc"])
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": f"{where}: {first['msg']}" if where else str(first["msg"]),
                "detail": detail,
            },
        )

    app.add_exception_handler(RequestValidationError, validation)
    app.add_exception_handler(DecisionInputError, decision_input)
    app.add_exception_handler(InferenceNotAuthorizedError, not_authorized)
    app.add_exception_handler(InvalidInputError, bad_text)
    app.add_exception_handler(ModelUnavailableError, unavailable)
    app.add_exception_handler(SourceNotPermittedError, source_denied)
    app.add_exception_handler(ScreeningNotFoundError, screening_missing)
    app.add_exception_handler(ReviewWriteDeniedError, write_denied)
    app.add_exception_handler(SourceRightsNotClearedError, rights)
    app.add_exception_handler(ProjectNotFoundError, not_found)
    app.add_exception_handler(UnknownMetricError, unknown_metric)
    app.add_exception_handler(InvalidQueryError, invalid)
    app.add_exception_handler(DatabaseNotReadyError, not_ready)
    app.add_exception_handler(OperationalError, not_ready)
