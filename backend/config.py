"""Application configuration.

Settings are read from environment variables and, if present, a ``.env`` file at
the repository root (see ``.env.example`` for the documented contract).

``SUPABASE_SERVICE_ROLE_KEY``, ``SUPABASE_JWT_SECRET``, and ``GEMINI_API_KEY``
are backend-only secrets. They must never be forwarded to the frontend or written to logs.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DATABASE_SCHEME = "postgresql+psycopg://"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        # A blank value (e.g. a copied .env.example) falls back to the default,
        # or counts as missing for required fields.
        env_ignore_empty=True,
        extra="ignore",
        # Keep rejected values (which may be secrets) out of validation errors.
        hide_input_in_errors=True,
    )

    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # Required: there is deliberately no default.
    DATABASE_URL: SecretStr

    # Accepts "a,b", a JSON array string, or a list (see validator below).
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    SUPABASE_URL: str | None = None
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_ANON_KEY: str | None = None  # Backward compatibility fallback

    # Backend-only secrets.
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = None
    SUPABASE_JWT_SECRET: SecretStr | None = None  # Isolated legacy fallback only
    GEMINI_API_KEY: SecretStr | None = None

    # AI Provider Configuration (Sprint 2 Free-First Architecture)
    AI_PROVIDER: str = "openrouter"
    AI_MODEL: str = "openrouter/free"
    OPENROUTER_API_KEY: SecretStr | None = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: float = 30.0
    OPENROUTER_HTTP_REFERER: str | None = None
    OPENROUTER_TITLE: str | None = None

    # Search & Discovery Configuration (Sprint 3 Overture + DuckDB Architecture)
    DISCOVERY_PROVIDER: str = "overture"  # 'overture' or 'mock'
    OVERTURE_S3_BUCKET: str = "overturemaps-us-west-2"
    OVERTURE_STAC_URL: str = "https://stac.overturemaps.org/catalog.json"
    OVERTURE_RELEASE: str | None = None  # None = dynamic resolution from STAC catalog
    OVERTURE_QUERY_TIMEOUT_SECONDS: float = 60.0
    SEARCH_DEFAULT_RADIUS_KM: float = 25.0
    SEARCH_MAX_LIMIT: int = 500
    SEARCH_WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    SEARCH_JOB_TIMEOUT_SECONDS: float = 300.0

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_psycopg_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(REQUIRED_DATABASE_SCHEME):
            raise ValueError(f"DATABASE_URL must start with '{REQUIRED_DATABASE_SCHEME}'")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def supabase_public_key(self) -> str | None:
        return self.SUPABASE_PUBLISHABLE_KEY or self.SUPABASE_ANON_KEY

    @property
    def supabase_auth_issuer(self) -> str:
        """Expected Supabase Auth JWT issuer."""
        if not self.SUPABASE_URL:
            return ""
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, built once on first use."""
    return Settings()  # type: ignore[call-arg]  # DATABASE_URL comes from the environment
