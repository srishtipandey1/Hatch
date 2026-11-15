from __future__ import annotations

import asyncio
import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.app.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_FALLBACK_MODEL,
    LLM_MODEL,
)

T = TypeVar("T", bound=BaseModel)
RETRY_DELAYS = (0.5, 1.0, 2.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 8.0


class LLMAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Normalise a Pydantic schema for providers that require strict JSON schema."""
    if isinstance(schema, dict):
        result = {key: _strict_schema(value) for key, value in schema.items()}
        if result.get("type") == "object" or "properties" in result:
            result["additionalProperties"] = False
            properties = result.get("properties")
            if isinstance(properties, dict) and properties:
                result["required"] = list(properties)
        return result
    if isinstance(schema, list):
        return [_strict_schema(item) for item in schema]
    return schema


class LLMGateway:
    def __init__(
        self,
        *,
        api_key: str = LLM_API_KEY,
        base_url: str = LLM_BASE_URL,
        model: str = LLM_MODEL,
        fallback_model: str = LLM_FALLBACK_MODEL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_model = fallback_model
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(45.0))
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        temperature: float = 0.2,
    ) -> T:
        if not self.api_key or not self.base_url or not self.model:
            raise RuntimeError("LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL are required for compilation.")
        schema_def = _strict_schema(schema.model_json_schema())
        schema_json = json.dumps(schema_def, ensure_ascii=False)
        system = f"{system}\nReturn the response as a json object matching the requested schema."
        prompt = user
        validation_problem = ""
        for attempt in range(2):
            payload = await self._completion(system, prompt, schema_def, temperature)
            content = payload["choices"][0]["message"].get("content")
            try:
                data = json.loads(content) if isinstance(content, str) else content
                return schema.model_validate(data)
            except (json.JSONDecodeError, ValidationError, TypeError) as error:
                validation_problem = str(error)[:1500]
                if attempt:
                    break
                prompt = (
                    "Return exactly one valid json object matching this schema. Correct the previous response; "
                    "do not add markdown or commentary.\n"
                    f"Schema: {schema_json}\n"
                    f"Validation problem: {validation_problem}\n"
                    f"Previous response: {str(content)[:6000]}"
                )
        raise LLMAPIError(502, f"The language model returned invalid structured data: {validation_problem}")

    async def text(self, *, system: str, user: str, temperature: float = 0.3) -> str:
        if not self.api_key or not self.base_url or not self.model:
            raise RuntimeError("LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL are required for runtime responses.")
        payload = await self._completion(system, user, None, temperature)
        content = payload["choices"][0]["message"].get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMAPIError(502, "The language model returned an empty response.")
        return content.strip()

    def _models(self) -> list[str]:
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)
        return models

    async def _completion(
        self,
        system: str,
        user: str,
        schema: dict[str, Any] | None,
        temperature: float,
    ) -> dict:
        last_error: LLMAPIError | None = None
        for model in self._models():
            body: dict[str, object] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
            }
            if schema is not None:
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": str(schema.get("title") or "response"),
                        "strict": True,
                        "schema": schema,
                    },
                }
            use_json_object = False
            for attempt in range(len(RETRY_DELAYS) + 1):
                try:
                    response = await self.client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=body,
                    )
                except httpx.HTTPError as error:
                    raise LLMAPIError(
                        502,
                        f"Language model connection failed ({type(error).__name__}).",
                    ) from error
                if schema is not None and response.status_code == 400 and not use_json_object:
                    use_json_object = True
                    body["response_format"] = {"type": "json_object"}
                    continue
                if response.status_code in RETRYABLE_STATUS and attempt < len(RETRY_DELAYS):
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = (
                            min(max(0.0, float(retry_after)), MAX_RETRY_AFTER_SECONDS)
                            if retry_after is not None
                            else RETRY_DELAYS[attempt]
                        )
                    except ValueError:
                        delay = RETRY_DELAYS[attempt]
                    await asyncio.sleep(delay)
                    continue
                break
            if response.is_error:
                last_error = self._error(response)
                if response.status_code in RETRYABLE_STATUS and model != self._models()[-1]:
                    continue
                raise last_error
            try:
                result = response.json()
            except ValueError as error:
                raise LLMAPIError(502, "Language model returned invalid JSON.") from error
            if not isinstance(result, dict) or not result.get("choices"):
                raise LLMAPIError(502, "Language model response did not contain a completion.")
            return result
        raise last_error or LLMAPIError(502, "Language model request failed.")

    def _error(self, response: httpx.Response) -> LLMAPIError:
        if response.status_code in {401, 403}:
            message = "Language model credentials or permissions were rejected."
        elif response.status_code == 402:
            message = "The language model provider reports a billing or quota issue."
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                message = f"The language model rate limit was reached. Retry after {retry_after} seconds."
            else:
                message = "The language model rate limit was reached. Retry after a short pause."
        elif response.status_code >= 500:
            message = "The language model service is temporarily unavailable."
        else:
            provider_message = ""
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    provider_message = str(error.get("message", error.get("code", "")))
                elif isinstance(error, str):
                    provider_message = error
            provider_message = provider_message.replace(self.api_key, "[REDACTED]")[:300]
            message = f"Language model request failed with HTTP {response.status_code}."
            if provider_message:
                message = f"{message} {provider_message}"
        return LLMAPIError(response.status_code, message)
