import asyncio
import json
import logging
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.middleware.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    register_error_handlers,
    unhandled_exception_handler,
    validation_error_handler,
)
from backend.schemas.common import ErrorDetail, ErrorResponse, HealthResponse


def make_request(path: str = "/example", request_id: str | None = None) -> Request:
    request = Request(
        {"type": "http", "method": "GET", "path": path, "query_string": b"", "headers": []}
    )
    if request_id is not None:
        request.state.request_id = request_id
    return request


def body_of(response) -> dict:
    return json.loads(response.body)


class Payload(BaseModel):
    name: str
    age: int


def make_validation_error() -> RequestValidationError:
    with pytest.raises(ValidationError) as exc_info:
        Payload.model_validate({"age": "not-a-number-secret"})
    return RequestValidationError(exc_info.value.errors())


# --- application errors ---


def test_app_error_uses_the_standard_shape():
    exc = AppError("CUSTOM_ERROR", "Something specific", status_code=409, details={"field": "x"})

    response = asyncio.run(app_error_handler(make_request(), exc))

    assert response.status_code == 409
    assert body_of(response) == {
        "error": {
            "code": "CUSTOM_ERROR",
            "message": "Something specific",
            "details": {"field": "x"},
        }
    }


def test_app_error_defaults_to_400_and_empty_details():
    response = asyncio.run(app_error_handler(make_request(), AppError("BAD", "Nope")))

    assert response.status_code == 400
    assert body_of(response)["error"]["details"] == {}


# --- validation errors ---


def test_validation_error_uses_the_standard_shape_and_does_not_echo_input():
    response = asyncio.run(validation_error_handler(make_request(), make_validation_error()))

    body = body_of(response)
    assert response.status_code == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed."

    errors = body["error"]["details"]["errors"]
    assert {tuple(error["loc"]) for error in errors} == {("name",), ("age",)}
    assert all(set(error) == {"loc", "message", "type"} for error in errors)
    assert "not-a-number-secret" not in response.body.decode()


# --- framework HTTP errors ---


def test_http_exception_uses_the_standard_shape():
    response = asyncio.run(http_exception_handler(make_request(), StarletteHTTPException(404)))

    assert response.status_code == 404
    assert body_of(response) == {
        "error": {"code": "NOT_FOUND", "message": "Not Found", "details": {}}
    }


def test_http_exception_keeps_custom_detail_and_headers():
    exc = StarletteHTTPException(
        401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )

    response = asyncio.run(http_exception_handler(make_request(), exc))

    assert response.status_code == 401
    assert body_of(response)["error"]["code"] == "UNAUTHORIZED"
    assert body_of(response)["error"]["message"] == "Not authenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_http_exception_with_structured_detail_moves_it_into_details():
    exc = StarletteHTTPException(400, detail={"reason": "bad input"})

    response = asyncio.run(http_exception_handler(make_request(), exc))

    error = body_of(response)["error"]
    assert error["code"] == "BAD_REQUEST"
    assert error["message"] == "Bad Request"
    assert error["details"] == {"detail": {"reason": "bad input"}}


def test_http_exception_with_unknown_status_code_falls_back():
    exc = StarletteHTTPException(599, detail="Custom failure")

    response = asyncio.run(http_exception_handler(make_request(), exc))

    assert response.status_code == 599
    assert body_of(response)["error"]["code"] == "HTTP_ERROR"
    assert body_of(response)["error"]["message"] == "Custom failure"


# --- unexpected errors ---


def raise_and_capture(message: str) -> Exception:
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        return exc


def test_unexpected_error_returns_safe_generic_response():
    exc = raise_and_capture("db password=hunter2 exploded")

    response = asyncio.run(unhandled_exception_handler(make_request(), exc))

    body = body_of(response)
    assert response.status_code == 500
    assert body == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        }
    }
    raw = response.body.decode()
    for leaked in ("hunter2", "RuntimeError", "Traceback", "raise_and_capture"):
        assert leaked not in raw


def test_unexpected_error_is_logged_with_traceback_and_request_id(caplog):
    exc = raise_and_capture("something broke")
    request = make_request(path="/boom", request_id="req-123")

    with caplog.at_level(logging.ERROR, logger="backend.middleware.errors"):
        asyncio.run(unhandled_exception_handler(request, exc))

    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    assert "/boom" in record.getMessage()
    assert record.exc_info is not None
    assert record.exc_info[1] is exc
    assert record.request_id == "req-123"


def test_unexpected_error_logging_works_without_a_request_id(caplog):
    exc = raise_and_capture("something broke")

    with caplog.at_level(logging.ERROR, logger="backend.middleware.errors"):
        asyncio.run(unhandled_exception_handler(make_request(), exc))

    assert caplog.records[0].request_id is None


# --- registration ---


def test_register_error_handlers_attaches_all_handlers():
    app = FastAPI()

    register_error_handlers(app)

    assert app.exception_handlers[AppError] is app_error_handler
    assert app.exception_handlers[RequestValidationError] is validation_error_handler
    assert app.exception_handlers[StarletteHTTPException] is http_exception_handler
    assert app.exception_handlers[Exception] is unhandled_exception_handler


# --- common schema serialization (kept here: only three test files are in scope) ---


def test_error_response_serializes_to_the_documented_contract():
    payload = ErrorResponse(error=ErrorDetail(code="SOME_CODE", message="Some message"))

    assert payload.model_dump(mode="json") == {
        "error": {"code": "SOME_CODE", "message": "Some message", "details": {}}
    }


def test_error_detail_accepts_structured_details():
    payload = ErrorResponse(
        error=ErrorDetail(code="C", message="M", details={"items": [1, 2], "nested": {"a": 1}})
    )

    assert payload.model_dump(mode="json")["error"]["details"] == {
        "items": [1, 2],
        "nested": {"a": 1},
    }


def test_health_response_serializes_with_default_version():
    payload = HealthResponse(
        status="healthy",
        database="connected",
        timestamp=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc),
    )

    assert payload.model_dump(mode="json") == {
        "status": "healthy",
        "database": "connected",
        "timestamp": "2026-10-05T12:00:00Z",
        "version": "0.1.0",
    }


@pytest.mark.parametrize(
    ("status", "database"),
    [("healthy", "unknown"), ("down", "connected")],
)
def test_health_response_rejects_unintended_values(status, database):
    with pytest.raises(ValidationError):
        HealthResponse(status=status, database=database, timestamp=datetime.now(timezone.utc))


def test_degraded_disconnected_is_a_valid_combination():
    payload = HealthResponse(
        status="degraded",
        database="disconnected",
        timestamp=datetime.now(timezone.utc),
    )

    assert payload.status == "degraded"
    assert payload.database == "disconnected"
