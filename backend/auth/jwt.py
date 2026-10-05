"""Supabase JWT verification using JWKS (asymmetric) with HS256 fallback."""

import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    PyJWTError,
)

from backend.config import Settings, get_settings
from backend.middleware.errors import AppError

logger = logging.getLogger(__name__)


class SupabaseJWTVerifier:
    """Verifies Supabase Auth JWTs.

    Prefers asymmetric JWKS verification from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
    Falls back to symmetric HS256 only when explicitly configured via `SUPABASE_JWT_SECRET`.
    """

    def __init__(
        self,
        jwks_url: str | None = None,
        jwks_client: jwt.PyJWKClient | None = None,
    ) -> None:
        self.jwks_url = jwks_url
        self._jwks_client = jwks_client
        if self._jwks_client is None and self.jwks_url:
            self._jwks_client = jwt.PyJWKClient(self.jwks_url, cache_jwk_set=True, lifespan=3600)

    def verify_token(self, token: str, settings: Settings | None = None) -> dict[str, Any]:
        """Verify JWT signature, issuer, audience, and expiration.

        Returns decoded payload dictionary.
        """
        if settings is None:
            settings = get_settings()

        expected_issuer = settings.supabase_auth_issuer
        expected_audience = "authenticated"

        try:
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")

            # Optional fallback for legacy HS256 secret if explicitly configured
            if alg == "HS256" and settings.SUPABASE_JWT_SECRET:
                secret = settings.SUPABASE_JWT_SECRET.get_secret_value()
                payload: dict[str, Any] = jwt.decode(
                    token,
                    secret,
                    algorithms=["HS256"],
                    audience=expected_audience,
                    issuer=expected_issuer,
                    options={"require": ["exp", "sub", "iss", "aud"]},
                )
            else:
                # Primary path: Asymmetric JWKS
                if self._jwks_client is None:
                    jwks_url = (
                        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
                        if settings.SUPABASE_URL
                        else None
                    )
                    if not jwks_url:
                        raise AppError(
                            "CONFIGURATION_ERROR",
                            "SUPABASE_URL is not configured for JWT verification",
                            status_code=500,
                        )
                    self.jwks_url = jwks_url
                    self._jwks_client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)

                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    audience=expected_audience,
                    issuer=expected_issuer,
                    options={"require": ["exp", "sub", "iss", "aud"]},
                )

            # Validate that sub is a valid UUID
            sub = payload.get("sub")
            if not sub:
                raise AppError(
                    "INVALID_TOKEN", "Token payload missing 'sub' claim", status_code=401
                )
            try:
                UUID(str(sub))
            except ValueError:
                raise AppError(
                    "INVALID_TOKEN", "Token 'sub' claim is not a valid UUID", status_code=401
                )

            return payload

        except ExpiredSignatureError:
            raise AppError("TOKEN_EXPIRED", "JWT has expired", status_code=401)
        except InvalidIssuerError:
            raise AppError("INVALID_ISSUER", "Token issuer does not match", status_code=401)
        except InvalidAudienceError:
            raise AppError("INVALID_AUDIENCE", "Token audience does not match", status_code=401)
        except AppError:
            raise
        except PyJWTError as e:
            logger.warning("JWT verification error: %s", type(e).__name__)
            raise AppError("INVALID_TOKEN", "Could not validate credentials", status_code=401)
        except Exception as e:
            logger.error("Unexpected error during JWT verification: %s", type(e).__name__)
            raise AppError("INVALID_TOKEN", "Could not validate credentials", status_code=401)


@lru_cache
def get_jwt_verifier() -> SupabaseJWTVerifier:
    """Return process-wide JWT verifier."""
    settings = get_settings()
    jwks_url = (
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        if settings.SUPABASE_URL
        else None
    )
    return SupabaseJWTVerifier(jwks_url=jwks_url)
