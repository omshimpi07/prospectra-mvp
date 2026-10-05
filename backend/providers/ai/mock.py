"""Mock AI Provider for testing and offline development."""

from backend.middleware.errors import AppError
from backend.schemas.icp import CompiledICPCriteria, LocationCriteria, TargetSignals


def get_default_mock_criteria(
    city: str = "Pune",
    service_offering: str = "Modern responsive website development and local SEO",
    target_categories: list[str] | None = None,
    has_website: bool | None = False,
) -> CompiledICPCriteria:
    """Return a standard valid CompiledICPCriteria fixture."""
    categories = target_categories or ["cafe", "bakery", "restaurant"]
    return CompiledICPCriteria(
        service_offering=service_offering,
        target_categories=categories,
        location=LocationCriteria(
            city=city,
            state_province="Maharashtra",
            country="IN",
            radius_km=25.0,
        ),
        signals=TargetSignals(
            has_website=has_website,
            min_rating=4.0,
            keywords=["specialty coffee", "artisan bakery"],
            negative_keywords=["fast food chain"],
        ),
        qualification_notes=[
            "Targets independent food & beverage businesses without an online presence."
        ],
    )


class MockAIProvider:
    """Mock implementation of AIProvider protocol."""

    def __init__(
        self,
        default_criteria: CompiledICPCriteria | None = None,
        error_to_raise: Exception | None = None,
    ) -> None:
        self.default_criteria = default_criteria or get_default_mock_criteria()
        self.error_to_raise = error_to_raise
        self.call_history: list[str] = []

    async def compile_icp(self, prompt: str) -> CompiledICPCriteria:
        self.call_history.append(prompt)

        if self.error_to_raise:
            raise self.error_to_raise

        if not prompt or not prompt.strip():
            raise AppError("INCOMPLETE_ICP_CRITERIA", "Prompt cannot be empty.", status_code=422)

        # Basic deterministic rule simulation for testing edge cases
        prompt_lower = prompt.lower()
        if "no location" in prompt_lower or "without city" in prompt_lower:
            raise AppError(
                "INCOMPLETE_ICP_CRITERIA",
                "Target location (city) is required and cannot be empty or UNKNOWN.",
                status_code=422,
            )

        if "no categories" in prompt_lower:
            raise AppError(
                "INCOMPLETE_ICP_CRITERIA",
                "No valid target business categories found in criteria.",
                status_code=422,
            )

        return self.default_criteria
