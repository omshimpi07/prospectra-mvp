"""Discovery Provider Protocol and Candidate Models."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.search import SearchSpecification


class DiscoveredCandidate(BaseModel):
    """Normalized business candidate discovered by an external provider."""

    model_config = ConfigDict(from_attributes=True)

    external_id: str = Field(..., description="Unique place identifier in provider")
    name: str = Field(..., min_length=1)
    canonical_category: str
    raw_category: str | None = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address: str | None = None
    city: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    website: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class DiscoveryProvider(Protocol):
    """Abstract interface for external place/business discovery providers."""

    async def discover_businesses(
        self,
        specification: SearchSpecification,
    ) -> list[DiscoveredCandidate]:
        """Execute place discovery against the external data source.

        Args:
            specification: Normalized SearchSpecification containing categories,
                           city, coordinates, and bounding box.

        Returns:
            List of DiscoveredCandidate objects.

        Raises:
            AppError: On provider timeout, connection failure, or query errors.
        """
        ...
