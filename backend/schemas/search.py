"""Search schemas and domain specifications."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SearchStatus = Literal["CREATED", "QUEUED", "RUNNING", "COMPLETED", "FAILED"]


class GeoBoundingBox(BaseModel):
    """Bounding box coordinates for spatial filtering."""

    min_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)
    min_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)


class SearchSpecification(BaseModel):
    """Normalized search criteria consumed by Discovery Providers."""

    target_categories: list[str] = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    state_province: str | None = None
    country: str | None = None
    center_lat: float = Field(..., ge=-90.0, le=90.0)
    center_lon: float = Field(..., ge=-180.0, le=180.0)
    radius_km: float = Field(default=25.0, ge=1.0, le=100.0)
    bounding_box: GeoBoundingBox
    limit: int = Field(default=100, ge=1, le=500)


class SearchCreate(BaseModel):
    """Request model for creating a new Search from an APPROVED ICP."""

    icp_id: UUID
    radius_km: float = Field(default=25.0, ge=1.0, le=100.0)
    limit: int = Field(default=100, ge=1, le=500)
    idempotency_key: str | None = Field(default=None, max_length=255)


class SearchResponse(BaseModel):
    """Full representation of a Search execution entity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    icp_id: UUID
    created_by: UUID
    status: SearchStatus
    idempotency_key: str | None = None
    specification: dict[str, Any]
    total_candidates: int
    new_candidates: int
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class SearchResultResponse(BaseModel):
    """Canonical representation of a discovered business candidate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    search_id: UUID
    workspace_id: UUID
    external_id: str
    provider: str
    name: str
    canonical_category: str
    raw_category: str | None = None
    latitude: float
    longitude: float
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    website: str | None = None
    confidence: float
    raw_metadata: dict[str, Any] | None = None
    created_at: datetime
