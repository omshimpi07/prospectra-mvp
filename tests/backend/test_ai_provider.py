"""Unit tests for AI Provider architecture and OpenRouter adapter."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from pydantic import SecretStr

from backend.config import Settings
from backend.middleware.errors import AppError
from backend.models.categories import (
    CANONICAL_CATEGORIES,
    normalize_category,
    validate_and_normalize_categories,
)
from backend.providers.ai.factory import get_ai_provider
from backend.providers.ai.mock import MockAIProvider
from backend.providers.ai.openrouter import OpenRouterAIAdapter
from backend.schemas.icp import CompiledICPCriteria


# --- Canonical Category Taxonomy Tests ---


def test_canonical_categories_membership():
    assert "restaurant" in CANONICAL_CATEGORIES
    assert "cafe" in CANONICAL_CATEGORIES
    assert "bakery" in CANONICAL_CATEGORIES
    assert "dental_clinic" in CANONICAL_CATEGORIES
    assert "unknown_category_xyz" not in CANONICAL_CATEGORIES


def test_normalize_category_direct_and_alias():
    assert normalize_category("Cafe") == "cafe"
    assert normalize_category("  restaurant  ") == "restaurant"
    assert normalize_category("cafes") == "cafe"
    assert normalize_category("coffee_shop") == "cafe"
    assert normalize_category("dentists") == "dental_clinic"
    assert normalize_category("random non-existent service") is None


def test_validate_and_normalize_categories():
    raw = ["Cafes", "bakeries", "random_junk", "cafe", "doctor"]
    normalized = validate_and_normalize_categories(raw)
    assert normalized == ["cafe", "bakery", "medical_clinic"]


# --- OpenRouter Adapter Tests ---


@pytest.fixture
def mock_openrouter_payload():
    return {
        "id": "gen-12345",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "service_offering": "Custom website development for local cafes",
                            "target_categories": ["cafes", "bakeries"],
                            "location": {
                                "city": "Pune",
                                "state_province": "Maharashtra",
                                "country": "IN",
                                "radius_km": 20.0,
                            },
                            "signals": {
                                "has_website": False,
                                "min_rating": 3.5,
                                "keywords": ["specialty coffee"],
                                "negative_keywords": ["starbucks"],
                            },
                            "qualification_notes": ["Independent shops only"],
                        }
                    ),
                }
            }
        ],
    }


@pytest.mark.anyio
async def test_openrouter_adapter_success(mock_openrouter_payload):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_openrouter_payload
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    adapter = OpenRouterAIAdapter(
        api_key=SecretStr("test-openrouter-key"),
        model="openrouter/free",
        client=mock_client,
    )

    criteria = await adapter.compile_icp("I build websites for bakeries in Pune without a website.")

    assert isinstance(criteria, CompiledICPCriteria)
    assert criteria.service_offering == "Custom website development for local cafes"
    assert criteria.target_categories == ["cafe", "bakery"]  # normalized
    assert criteria.location.city == "Pune"
    assert criteria.signals.has_website is False

    # Check payload sent to OpenRouter
    call_args = mock_client.post.call_args
    assert call_args is not None
    _, kwargs = call_args
    json_body = kwargs["json"]
    assert json_body["model"] == "openrouter/free"
    assert json_body["response_format"]["type"] == "json_schema"
    assert json_body["response_format"]["json_schema"]["name"] == "compiled_icp_criteria"
    assert json_body["response_format"]["json_schema"]["strict"] is True


@pytest.mark.anyio
async def test_openrouter_adapter_attribution_headers():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "service_offering": "SEO for salons",
                            "target_categories": ["salon"],
                            "location": {"city": "Mumbai"},
                        }
                    )
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    # Test with attribution headers
    adapter_with_headers = OpenRouterAIAdapter(
        api_key=SecretStr("key"),
        http_referer="http://localhost:3000",
        title="Prospectra Local Dev",
        client=mock_client,
    )
    headers = adapter_with_headers._build_headers()
    assert headers["HTTP-Referer"] == "http://localhost:3000"
    assert headers["X-Title"] == "Prospectra Local Dev"
    assert headers["Authorization"] == "Bearer key"

    # Test without attribution headers (omitted by default)
    adapter_no_headers = OpenRouterAIAdapter(api_key=SecretStr("key"))
    headers_clean = adapter_no_headers._build_headers()
    assert "HTTP-Referer" not in headers_clean
    assert "X-Title" not in headers_clean


@pytest.mark.anyio
async def test_openrouter_adapter_empty_prompt():
    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"))
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("   ")
    assert exc_info.value.code == "INCOMPLETE_ICP_CRITERIA"
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_openrouter_adapter_missing_api_key():
    adapter = OpenRouterAIAdapter(api_key=None)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_PROVIDER_AUTHENTICATION_ERROR"
    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_openrouter_adapter_rate_limit_429():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "Rate limit reached"
    error = httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=mock_response)
    mock_client.post.side_effect = error

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_RATE_LIMIT_EXCEEDED"
    assert exc_info.value.status_code == 429


@pytest.mark.anyio
async def test_openrouter_adapter_auth_error_401():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    error = httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=mock_response)
    mock_client.post.side_effect = error

    adapter = OpenRouterAIAdapter(api_key=SecretStr("invalid-key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_PROVIDER_AUTHENTICATION_ERROR"
    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_openrouter_adapter_timeout_504():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_PROVIDER_UNAVAILABLE"
    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_openrouter_adapter_connection_error_504():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = httpx.ConnectError("Network unreachable")

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_PROVIDER_UNAVAILABLE"
    assert exc_info.value.status_code == 504


@pytest.mark.anyio
async def test_openrouter_adapter_malformed_json():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Not a valid JSON string {"}}]
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Valid prompt")
    assert exc_info.value.code == "AI_MALFORMED_OUTPUT"
    assert exc_info.value.status_code == 502


@pytest.mark.anyio
async def test_openrouter_adapter_strict_geography_rejects_empty_or_unknown_city():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    # Model returned "UNKNOWN" as city
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "service_offering": "Web development",
                            "target_categories": ["cafe"],
                            "location": {"city": "UNKNOWN"},
                        }
                    )
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Prompt with no city")
    assert exc_info.value.code == "INCOMPLETE_ICP_CRITERIA"
    assert exc_info.value.status_code == 422


@pytest.mark.anyio
async def test_openrouter_adapter_rejects_missing_categories():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    # Model returned only non-canonical junk categories
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "service_offering": "Web development",
                            "target_categories": ["nonexistent_alien_business"],
                            "location": {"city": "Pune"},
                        }
                    )
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    adapter = OpenRouterAIAdapter(api_key=SecretStr("key"), client=mock_client)
    with pytest.raises(AppError) as exc_info:
        await adapter.compile_icp("Prompt with invalid categories")
    assert exc_info.value.code == "INCOMPLETE_ICP_CRITERIA"
    assert exc_info.value.status_code == 422


# --- Mock AI Provider Tests ---


@pytest.mark.anyio
async def test_mock_ai_provider():
    provider = MockAIProvider()
    criteria = await provider.compile_icp("I build websites for Pune cafes")
    assert criteria.location.city == "Pune"
    assert "cafe" in criteria.target_categories
    assert len(provider.call_history) == 1

    # Simulate simulated incomplete criteria
    with pytest.raises(AppError) as exc_info:
        await provider.compile_icp("no location provided")
    assert exc_info.value.code == "INCOMPLETE_ICP_CRITERIA"


# --- Provider Factory Tests ---


def test_get_ai_provider_factory(test_settings: Settings):
    # Test mock provider selection
    test_settings.AI_PROVIDER = "mock"
    mock_prov = get_ai_provider(test_settings)
    assert isinstance(mock_prov, MockAIProvider)

    # Test openrouter provider selection
    test_settings.AI_PROVIDER = "openrouter"
    test_settings.OPENROUTER_API_KEY = SecretStr("mock-key")
    openrouter_prov = get_ai_provider(test_settings)
    assert isinstance(openrouter_prov, OpenRouterAIAdapter)

    # Test invalid provider
    test_settings.AI_PROVIDER = "unsupported_provider"
    with pytest.raises(ValueError):
        get_ai_provider(test_settings)
