"""Pydantic schemas for Prospect, Qualification Evidence, and Scoring."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ProspectStatus = Literal["QUEUED", "RESEARCHING", "COMPLETED", "FAILED"]
QualificationStatus = Literal["UNQUALIFIED", "QUALIFIED", "DISQUALIFIED", "REVIEW_NEEDED"]
ReviewStatus = Literal["UNREVIEWED", "APPROVED", "REJECTED"]
FactorStatus = Literal["matched", "unmatched", "unknown"]


class ReviewProspectRequest(BaseModel):
    """Request payload to record a human review decision on a prospect."""

    review_status: ReviewStatus = Field(
        ..., description="Human review decision: 'UNREVIEWED', 'APPROVED', or 'REJECTED'."
    )
    rejection_reason: str | None = Field(
        default=None,
        max_length=100,
        description="Reason for rejection. Mandatory if review_status is 'REJECTED'.",
    )
    seller_note: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional qualitative note recorded by the seller.",
    )

    @model_validator(mode="after")
    def _validate_rejection_reason(self) -> "ReviewProspectRequest":
        if self.review_status == "REJECTED":
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection_reason is required when review_status is 'REJECTED'.")
            self.rejection_reason = self.rejection_reason.strip()
        else:
            # When changing away from REJECTED, rejection_reason is cleared to None
            self.rejection_reason = None
        return self


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


class ScoreFactor(BaseModel):
    """Individual factor contributing to a prospect's opportunity score."""

    key: str
    label: str
    impact: float
    max_impact: float
    status: FactorStatus
    evidence_snippet: str | None = None


class ScoreBreakdown(BaseModel):
    """Auditable mathematical decomposition of a prospect's priority score."""

    raw_score: float
    status_multiplier: float
    priority_score: float
    scoring_profile: str
    scoring_version: str = "v1.0"
    scored_at: datetime
    factors: list[ScoreFactor] = Field(default_factory=list)


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
    priority_score: float = 0.0
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    scoring_version: str = "v1.0"
    scored_at: datetime | None = None
    qualification_reason: str | None = None
    raw_signals: dict[str, Any] = Field(default_factory=dict)
    review_status: ReviewStatus = "UNREVIEWED"
    rejection_reason: str | None = None
    seller_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: UUID | None = None
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

    @field_validator("score_breakdown", mode="before")
    @classmethod
    def _default_score_breakdown(cls, v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}

    @field_validator("priority_score", mode="before")
    @classmethod
    def _default_priority_score(cls, v: Any) -> float:
        return float(v) if v is not None else 0.0

    @field_validator("scoring_version", mode="before")
    @classmethod
    def _default_scoring_version(cls, v: Any) -> str:
        return str(v) if v is not None else "v1.0"

    @field_validator("review_status", mode="before")
    @classmethod
    def _default_review_status(cls, v: Any) -> str:
        return str(v) if v is not None else "UNREVIEWED"


class RescoreResponse(BaseModel):
    """Response returned upon completing workspace re-scoring."""

    rescored_count: int = Field(..., description="Number of prospects re-scored.")
    message: str = Field(..., description="Summary message.")
