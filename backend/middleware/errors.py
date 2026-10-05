"""Standardized error handling.

Every handler returns the same body shape (see ``ErrorResponse``)::

    {"error": {"code": "ERROR_CODE", "message": "...", "details": {}}}

Unexpected failures return a generic message to the client; the full traceback
goes to the logs only. If a request-ID middleware later sets
``request.state.request_id``, it is attached to that log record automatically.
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """A known, client-facing application error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details or {}))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Only location, message and type are returned: pydantic's "input" field
    # would echo submitted values back to the client.
    errors = [
        {"loc": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return _error_response(
        422, "VALIDATION_ERROR", "Request validation failed.", {"errors": errors}
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Keep framework errors (404, 405, ...) in the standard shape too."""
    try:
        status = HTTPStatus(exc.status_code)
        code, phrase = status.name, status.phrase
    except ValueError:
        code, phrase = "HTTP_ERROR", "HTTP error"

    if isinstance(exc.detail, str) and exc.detail:
        message, details = exc.detail, None
    else:
        message, details = phrase, {"detail": exc.detail} if exc.detail else None
    return _error_response(exc.status_code, code, message, details, exc.headers)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,  # path only: the query string may carry tokens
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _error_response(500, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    """Attach all handlers to a FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
