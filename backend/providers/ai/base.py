"""AI Provider Protocol."""

from typing import Protocol, runtime_checkable

from backend.schemas.icp import CompiledICPCriteria


@runtime_checkable
class AIProvider(Protocol):
    """Abstract protocol for AI compilation providers."""

    async def compile_icp(self, prompt: str) -> CompiledICPCriteria:
        """Compile a natural-language seller prompt into structured ICP criteria.

        Raises:
            AppError: On rate limit (429), auth error (502), timeout/unavailability (504),
                      upstream error (502), malformed output (502), or incomplete criteria (422).
        """
        ...
