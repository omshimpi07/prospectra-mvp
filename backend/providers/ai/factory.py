"""AI Provider Factory."""

from backend.config import Settings, get_settings
from backend.providers.ai.base import AIProvider
from backend.providers.ai.mock import MockAIProvider
from backend.providers.ai.openrouter import OpenRouterAIAdapter


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    """Instantiate and return the configured AIProvider implementation."""
    cfg = settings or get_settings()

    if cfg.AI_PROVIDER == "openrouter":
        return OpenRouterAIAdapter(
            api_key=cfg.OPENROUTER_API_KEY,
            model=cfg.AI_MODEL,
            base_url=cfg.OPENROUTER_BASE_URL,
            timeout=cfg.OPENROUTER_TIMEOUT_SECONDS,
            http_referer=cfg.OPENROUTER_HTTP_REFERER,
            title=cfg.OPENROUTER_TITLE,
        )
    if cfg.AI_PROVIDER == "mock":
        return MockAIProvider()

    raise ValueError(f"Unsupported AI_PROVIDER: {cfg.AI_PROVIDER}")
