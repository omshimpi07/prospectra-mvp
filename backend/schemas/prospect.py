"""Pydantic schemas for Prospect and Qualification Evidence."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProspectStatus = Literal["QUEUED", "RESEARCHING", "COMPLETED", "FAILED"]
QualificationStatus = Literal["UNQUALIFIED", "QUALIFIED", "DISQUALIFIED", "REVIEW_NEEDED"]


class QualifyCandidatesRequest(BaseModel):
    """Request payload to promote search results into the qualification pipeline."""

    search_result_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of search result IDs to qualify.",
    )


class QualifyCandidatesResponse(BaseModel):
    """Response returned upon enqueuing candidates for qualification."""

    enqueued_count: int = Field(..., description="Number of candidates queued for qualification.")
    prospect_ids: list[UUID] = Field(..., description="IDs of created or existing prospects.")
    message: str = Field(..., description="Status summary message.")


class EvidenceResponse(BaseModel):
    """Atomic auditable observation supporting qualification."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    prospect_id: UUID
    signal_key: str
    signal_value: dict[str, Any]
    confidence: float
    source_url: str | None = None
    snippet: str | None = None
    observed_at: datetime
    created_at: datetime


class ProspectResponse(BaseModel):
    """Canonical prospect entity within the workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    icp_id: UUID
    search_result_id: UUID | None = None
    name: str
    canonical_category: str
    city: str | None = None
    website_url: str | None = None
    phone: str | None = None
    status: ProspectStatus
    qualification_status: QualificationStatus
    fit_score: float
    qualification_reason: str | None = None
    raw_signals: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    qualified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("raw_signals", mode="before")
    @classmethod
    def _default_raw_signals(cls, v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}
