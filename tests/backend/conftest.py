"""Shared test fixtures and mock helpers."""

import time
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr

from backend.auth.jwt import SupabaseJWTVerifier
from backend.config import Settings


# Generate a persistent test RSA keypair for RS256 token signing
@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_key, public_pem


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        DATABASE_URL=SecretStr("postgresql+psycopg://test:test@localhost:5432/test"),
        SUPABASE_URL="https://testproject.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_test_publishable_key",
        SUPABASE_JWT_SECRET=SecretStr("test_symmetric_secret_key_32_bytes_long!!"),
        ENVIRONMENT="development",
    )


@pytest.fixture
def make_token(rsa_keypair, test_settings):
    private_key, _ = rsa_keypair

    def _generator(
        sub: str | None = None,
        email: str = "test@example.com",
        exp_delta: int = 3600,
        issuer: str | None = None,
        audience: str | None = "authenticated",
        algorithm: str = "RS256",
        secret_key: str | None = None,
    ) -> str:
        now = int(time.time())
        payload = {
            "sub": sub or str(uuid4()),
            "email": email,
            "aud": audience,
            "iss": issuer or test_settings.supabase_auth_issuer,
            "iat": now,
            "exp": now + exp_delta,
        }
        if algorithm == "HS256":
            secret = secret_key or test_settings.SUPABASE_JWT_SECRET.get_secret_value()
            return jwt.encode(payload, secret, algorithm="HS256")
        return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-key-id"})

    return _generator


@pytest.fixture
def mock_verifier(rsa_keypair, test_settings):
    _, public_pem = rsa_keypair
    verifier = SupabaseJWTVerifier(
        jwks_url=f"{test_settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    )

    mock_key = MagicMock()
    mock_key.key = public_pem
    mock_jwks_client = MagicMock()
    mock_jwks_client.get_signing_key_from_jwt.return_value = mock_key
    verifier._jwks_client = mock_jwks_client

    return verifier
