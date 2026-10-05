"""ICP schemas and domain models."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ICPStatus = Literal["DRAFT", "COMPILED", "APPROVED", "ARCHIVED"]


class LocationCriteria(BaseModel):
    """Target geographic bounds.

    Strict zero-hallucination constraint: City must be explicitly provided in user intent;
    never fabricated or defaulted to 'UNKNOWN'.
    """

    city: str = Field(..., min_length=1, description="Target city name.")
    state_province: str | None = Field(
        default=None, description="State, province, or region if specified."
    )
    country: str | None = Field(default=None, description="Country code or name if specified.")
    radius_km: float | None = Field(
        default=None, ge=1.0, le=500.0, description="Target radius in km."
    )


class TargetSignals(BaseModel):
    """Signals used for qualifying or filtering target businesses."""

    has_website: bool | None = Field(
        default=None,
        description="Filter by presence (true) or absence (false) of website, or any (None).",
    )
    min_rating: float | None = Field(
        default=None, ge=1.0, le=5.0, description="Minimum customer rating."
    )
    keywords: list[str] = Field(default_factory=list, description="Keywords to match in listings.")
    negative_keywords: list[str] = Field(
        default_factory=list, description="Keywords to exclude from listings."
    )


class CompiledICPCriteria(BaseModel):
    """Validated structured specification extracted from seller's natural language input."""

    service_offering: str = Field(
        ..., min_length=1, description="Normalized seller service offering."
    )
    target_categories: list[str] = Field(
        ..., min_length=1, description="List of validated canonical business categories."
    )
    location: LocationCriteria
    signals: TargetSignals = Field(default_factory=TargetSignals)
    qualification_notes: list[str] = Field(
        default_factory=list, description="Contextual qualification notes or rationale."
    )


class ICPCreate(BaseModel):
    """Request model for creating a new ICP draft."""

    name: str = Field(..., min_length=1, max_length=255)
    raw_prompt: str = Field(..., min_length=1)


class ICPUpdate(BaseModel):
    """Request model for updating an existing ICP or transitioning its status.

    workspace_id and created_by are strictly forbidden from modification.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    raw_prompt: str | None = Field(None, min_length=1)
    status: ICPStatus | None = None


class ICPResponse(BaseModel):
    """Full representation of an ICP entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    created_by: UUID
    name: str
    raw_prompt: str
    status: ICPStatus
    version: int
    compiled_criteria: dict[str, Any] | None = None
    compilation_error: str | None = None
    created_at: datetime
    updated_at: datetime
