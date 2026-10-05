"""Mock Discovery Provider for offline development and deterministic testing."""

from backend.providers.discovery.base import DiscoveredCandidate
from backend.schemas.search import SearchSpecification


def get_default_mock_candidates(city: str = "Pune", count: int = 5) -> list[DiscoveredCandidate]:
    """Generate deterministic sample business candidates for a given city."""
    sample_names = [
        (
            "Blue Tokai Coffee Roasters",
            "cafe",
            "coffee_shop",
            18.5362,
            73.8941,
            "Koregaon Park, Pune",
        ),
        ("German Bakery", "bakery", "bakery", 18.5358, 73.8967, "North Main Road, Pune"),
        ("Vaishali Restaurant", "restaurant", "restaurant", 18.5204, 73.8415, "FC Road, Pune"),
        ("Le Plaisir Patisserie", "cafe", "pastry_shop", 18.5144, 73.8344, "Prabhat Road, Pune"),
        (
            "The French Window Patisserie",
            "bakery",
            "bakery",
            18.5385,
            73.8988,
            "Koregaon Park, Pune",
        ),
        (
            "Chitale Bandhu Mithaiwale",
            "bakery",
            "pastry_shop",
            18.5173,
            73.8524,
            "Bajirao Road, Pune",
        ),
        ("Kayani Bakery", "bakery", "bakery", 18.5165, 73.8781, "East Street, Camp, Pune"),
    ]

    candidates: list[DiscoveredCandidate] = []
    for i, (name, cat, raw_cat, lat, lon, addr) in enumerate(sample_names[:count]):
        candidates.append(
            DiscoveredCandidate(
                external_id=f"overture-mock-{city.lower()}-{i + 1:03d}",
                name=name,
                canonical_category=cat,
                raw_category=raw_cat,
                latitude=lat,
                longitude=lon,
                address=addr,
                city=city,
                postal_code="411001",
                phone="+91-20-26123456",
                website=f"https://{name.lower().replace(' ', '')}.in" if i % 2 == 0 else None,
                confidence=0.95,
                raw_metadata={"mock": True, "source": "synthetic_fixtures"},
            )
        )
    return candidates


class MockDiscoveryProvider:
    """Mock implementation of DiscoveryProvider protocol."""

    def __init__(
        self,
        candidates: list[DiscoveredCandidate] | None = None,
        error_to_raise: Exception | None = None,
    ) -> None:
        self.candidates = candidates
        self.error_to_raise = error_to_raise
        self.call_history: list[SearchSpecification] = []

    async def discover_businesses(
        self,
        specification: SearchSpecification,
    ) -> list[DiscoveredCandidate]:
        self.call_history.append(specification)

        if self.error_to_raise:
            raise self.error_to_raise

        if self.candidates is not None:
            # Filter provided candidates by target categories
            target_cats = set(specification.target_categories)
            return [c for c in self.candidates if c.canonical_category in target_cats][
                : specification.limit
            ]

        # Generate default synthetic candidates matching specification
        all_mock = get_default_mock_candidates(city=specification.city, count=10)
        target_cats = set(specification.target_categories)
        filtered = [c for c in all_mock if c.canonical_category in target_cats]
        return filtered[: specification.limit]
