"""OpenRouter AI Provider Adapter.

Implements structured JSON output extraction via OpenRouter API with
strict JSON schema enforcement and deterministic domain validation.
"""

import json
import logging
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from backend.middleware.errors import AppError
from backend.models.categories import CANONICAL_CATEGORIES, validate_and_normalize_categories
from backend.schemas.icp import CompiledICPCriteria

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = f"""You are the Prospectra ICP Extraction Engine.
Your task is to analyze a seller's natural-language description of what they sell and who they target,
and extract a structured, validated Ideal Customer Profile (ICP) according to the schema.

RULES:
1. Target Categories MUST only be selected from the following canonical categories:
{sorted(CANONICAL_CATEGORIES)}
Do not invent categories. Map user-mentioned businesses into these canonical types.

2. Geography:
- Extract target city, state/province, country, and radius in kilometers.
- STRICT RULE: NEVER fabricate or hallucinate a city or location.
- If the user's prompt DOES NOT explicitly mention a target city or location, set the city field to an empty string (""). Do NOT default to Pune, India, or "UNKNOWN".

3. Signals & Filters:
- If user mentions targeting businesses without websites, set has_website to false.
- If user mentions targeting businesses with websites, set has_website to true.
- Extract relevant keywords, negative keywords, or rating requirements if mentioned.

4. Output MUST conform strictly to the provided JSON Schema.
"""


class OpenRouterAIAdapter:
    """AIProvider implementation connecting to OpenRouter API."""

    def __init__(
        self,
        api_key: SecretStr | str | None,
        model: str = "openrouter/free",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 30.0,
        http_referer: str | None = None,
        title: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if isinstance(api_key, SecretStr):
            self._api_key = api_key.get_secret_value()
        else:
            self._api_key = api_key or ""

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http_referer = http_referer
        self.title = title
        self._client = client

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.title:
            headers["X-Title"] = self.title
        return headers

    async def compile_icp(self, prompt: str) -> CompiledICPCriteria:
        """Send prompt to OpenRouter and return validated CompiledICPCriteria."""
        if not prompt or not prompt.strip():
            raise AppError(
                "INCOMPLETE_ICP_CRITERIA",
                "Prompt cannot be empty.",
                status_code=422,
            )

        if not self._api_key:
            raise AppError(
                "AI_PROVIDER_AUTHENTICATION_ERROR",
                "OpenRouter API key is not configured.",
                status_code=502,
            )

        schema = CompiledICPCriteria.model_json_schema()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": prompt.strip()},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "compiled_icp_criteria",
                    "strict": True,
                    "schema": schema,
                },
            },
            "temperature": 0.1,
        }

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()

        response_data: dict[str, Any] = {}
        try:
            if self._client:
                response = await self._client.post(
                    url, json=payload, headers=headers, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            response_data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("OpenRouter request timed out: %s", exc)
            raise AppError(
                "AI_PROVIDER_UNAVAILABLE",
                "AI provider request timed out.",
                status_code=504,
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.warning("OpenRouter HTTP error: %s (body=%s)", status, exc.response.text)
            if status == 429:
                raise AppError(
                    "AI_RATE_LIMIT_EXCEEDED",
                    "OpenRouter rate limit reached. Retry shortly.",
                    status_code=429,
                ) from exc
            if status in (401, 403):
                raise AppError(
                    "AI_PROVIDER_AUTHENTICATION_ERROR",
                    "Invalid or unauthorized AI gateway credentials.",
                    status_code=502,
                ) from exc
            if status >= 500:
                raise AppError(
                    "AI_PROVIDER_ERROR",
                    f"OpenRouter upstream error ({status}).",
                    status_code=502,
                ) from exc
            raise AppError(
                "AI_PROVIDER_ERROR",
                f"OpenRouter request failed ({status}).",
                status_code=502,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("OpenRouter connection error: %s", exc)
            raise AppError(
                "AI_PROVIDER_UNAVAILABLE",
                "Failed to connect to AI provider.",
                status_code=504,
            ) from exc

        return self._parse_and_validate_response(response_data)

    def _parse_and_validate_response(self, response_data: dict[str, Any]) -> CompiledICPCriteria:
        """Parse response payload, apply Pydantic validation, and enforce deterministic rules."""
        choices = response_data.get("choices")
        if not choices or not isinstance(choices, list):
            raise AppError(
                "AI_MALFORMED_OUTPUT",
                "Empty response from AI provider.",
                status_code=502,
            )

        message = choices[0].get("message", {})
        content = message.get("content")
        if not content or not isinstance(content, str):
            raise AppError(
                "AI_MALFORMED_OUTPUT",
                "AI provider returned empty content.",
                status_code=502,
            )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AppError(
                "AI_MALFORMED_OUTPUT",
                "Failed to parse JSON response from AI provider.",
                status_code=502,
            ) from exc

        try:
            raw_criteria = CompiledICPCriteria.model_validate(parsed)
        except ValidationError as exc:
            raise AppError(
                "AI_MALFORMED_OUTPUT",
                "AI response failed schema validation.",
                status_code=502,
                details={"errors": exc.errors()},
            ) from exc

        # 1. Deterministic Category Taxonomy Normalization & Validation
        normalized_categories = validate_and_normalize_categories(raw_criteria.target_categories)
        if not normalized_categories:
            raise AppError(
                "INCOMPLETE_ICP_CRITERIA",
                "No valid target business categories found in criteria.",
                status_code=422,
            )

        # 2. Strict Geography Validation (Never allow empty or hallucinated UNKNOWN)
        city = raw_criteria.location.city.strip()
        if not city or city.upper() in ("UNKNOWN", "N/A", "NONE", "NULL"):
            raise AppError(
                "INCOMPLETE_ICP_CRITERIA",
                "Target location (city) is required and cannot be empty or UNKNOWN.",
                status_code=422,
            )

        # 3. Construct validated criteria
        validated_location = raw_criteria.location.model_copy(update={"city": city})
        return raw_criteria.model_copy(
            update={
                "target_categories": normalized_categories,
                "location": validated_location,
            }
        )
