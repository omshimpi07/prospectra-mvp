"""Reusable API response models."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    database: Literal["connected", "disconnected"]
    timestamp: datetime
    version: str = "0.1.0"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error body: ``{"error": {"code", "message", "details"}}``."""

    error: ErrorDetail
