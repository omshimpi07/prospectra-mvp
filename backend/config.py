"""Application configuration.

Settings are read from environment variables and, if present, a ``.env`` file at
the repository root (see ``.env.example`` for the documented contract).

``SUPABASE_SERVICE_ROLE_KEY`` and ``GEMINI_API_KEY`` are backend-only secrets.
They must never be forwarded to the frontend or written to logs.
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
    SUPABASE_ANON_KEY: str | None = None

    # Backend-only secrets.
    SUPABASE_SERVICE_ROLE_KEY: SecretStr | None = None
    GEMINI_API_KEY: SecretStr | None = None

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


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, built once on first use."""
    return Settings()  # type: ignore[call-arg]  # DATABASE_URL comes from the environment
