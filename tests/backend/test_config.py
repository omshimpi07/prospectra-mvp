import pytest
from pydantic import ValidationError

from backend.config import Settings, get_settings

SETTINGS_ENV_VARS = (
    "ENVIRONMENT",
    "DEBUG",
    "DATABASE_URL",
    "CORS_ORIGINS",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "GEMINI_API_KEY",
)
TEST_DATABASE_URL = "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_settings() -> Settings:
    # _env_file=None keeps a developer's real .env out of the test.
    return Settings(_env_file=None)


def test_development_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    settings = build_settings()

    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is False
    assert settings.CORS_ORIGINS == ["http://localhost:3000"]
    assert settings.SUPABASE_URL is None
    assert settings.SUPABASE_ANON_KEY is None
    assert settings.SUPABASE_SERVICE_ROLE_KEY is None
    assert settings.GEMINI_API_KEY is None


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example-project.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-value")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-value")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-value")

    settings = build_settings()

    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is True
    assert settings.DATABASE_URL.get_secret_value() == TEST_DATABASE_URL
    assert settings.SUPABASE_URL == "https://example-project.supabase.co"
    assert settings.SUPABASE_ANON_KEY == "anon-test-value"
    assert settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value() == "service-role-test-value"
    assert settings.GEMINI_API_KEY.get_secret_value() == "gemini-test-value"


def test_invalid_environment_name_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "qa")

    with pytest.raises(ValidationError):
        build_settings()


def test_database_url_is_required():
    with pytest.raises(ValidationError) as exc_info:
        build_settings()

    assert "DATABASE_URL" in str(exc_info.value)


def test_blank_database_url_counts_as_missing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")

    with pytest.raises(ValidationError):
        build_settings()


def test_blank_optional_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("CORS_ORIGINS", "")

    settings = build_settings()

    assert settings.ENVIRONMENT == "development"
    assert settings.SUPABASE_URL is None
    assert settings.CORS_ORIGINS == ["http://localhost:3000"]


@pytest.mark.parametrize(
    "bad_url",
    [
        "postgresql://user:not-a-real-password@localhost:5432/db",
        "postgresql+asyncpg://user:not-a-real-password@localhost:5432/db",
        "mysql://user:not-a-real-password@localhost:3306/db",
    ],
)
def test_database_url_must_use_psycopg_driver(monkeypatch, bad_url):
    monkeypatch.setenv("DATABASE_URL", bad_url)

    with pytest.raises(ValidationError) as exc_info:
        build_settings()

    assert "postgresql+psycopg://" in str(exc_info.value)
    assert "not-a-real-password" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:3000", ["http://localhost:3000"]),
        (
            "http://localhost:3000,https://example.com",
            ["http://localhost:3000", "https://example.com"],
        ),
        (
            " http://localhost:3000 , https://example.com ,",
            ["http://localhost:3000", "https://example.com"],
        ),
        (
            '["http://localhost:3000", "https://example.com"]',
            ["http://localhost:3000", "https://example.com"],
        ),
    ],
)
def test_cors_origins_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("CORS_ORIGINS", raw)

    settings = build_settings()

    assert isinstance(settings.CORS_ORIGINS, list)
    assert settings.CORS_ORIGINS == expected


def test_malformed_json_cors_origins_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:3000"')

    with pytest.raises(ValidationError):
        build_settings()


def test_secrets_do_not_appear_in_repr_or_str(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-value")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-value")

    settings = build_settings()
    rendered = repr(settings) + str(settings)

    assert "test_password" not in rendered
    assert "service-role-test-value" not in rendered
    assert "gemini-test-value" not in rendered


def test_env_file_is_loaded_and_unknown_keys_are_ignored(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"DATABASE_URL={TEST_DATABASE_URL}",
                "ENVIRONMENT=staging",
                "SUPABASE_URL=",
                "SOME_UNRELATED_VARIABLE=1",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.ENVIRONMENT == "staging"
    assert settings.SUPABASE_URL is None


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    first = get_settings()
    second = get_settings()
    get_settings.cache_clear()
    third = get_settings()

    assert first is second
    assert third is not first
