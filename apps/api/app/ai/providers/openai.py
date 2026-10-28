import json
import logging
import time

from openai import AsyncOpenAI, OpenAIError

from app.ai.cost_tracking import log_ai_call
from app.ai.exceptions import AIProviderError
from app.ai.providers.base import AIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """
    Real OpenAI chat-completions integration.

    Falls back to a clearly-labeled placeholder (instead of raising) when
    OPENAI_API_KEY isn't configured, so local/dev environments without a key
    keep working — every other real API error is still raised so callers
    (Celery tasks, etc.) can retry/fail as appropriate.
    """

    def __init__(self):
        self._client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        )

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        *,
        task: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> str:
        model = model or settings.AI_MODEL

        if self._client is None:
            logger.warning(
                "OPENAI_API_KEY not configured — returning a placeholder "
                "response instead of calling OpenAI."
            )
            return (
                "[AI unavailable] OPENAI_API_KEY is not configured, so no "
                "model was called. Set OPENAI_API_KEY to enable real AI "
                "analysis."
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
            )
        except OpenAIError as exc:
            logger.exception("OpenAI API call failed")
            raise AIProviderError(
                f"OpenAI call failed: {exc}", task=task, provider="openai"
            ) from exc
        duration_ms = int((time.monotonic() - start) * 1000)

        usage = response.usage
        log_ai_call(
            task=task or "unknown",
            provider="openai",
            model=model,
            duration_ms=duration_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            prompt_version=prompt_version,
        )

        return response.choices[0].message.content or ""

    async def generate_json(
        self,
        prompt: str,
        system: str | None = None,
        *,
        task: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
    ) -> dict:
        """
        Same as generate(), but forces JSON-object output and parses it.
        Used by callers (e.g. ClaimAnalyzer) that need structured fields
        instead of freeform prose.
        """
        model = model or settings.AI_MODEL

        if self._client is None:
            logger.warning(
                "OPENAI_API_KEY not configured — returning a placeholder "
                "response instead of calling OpenAI."
            )
            return {
                "error": "ai_unavailable",
                "detail": (
                    "OPENAI_API_KEY is not configured, so no model was "
                    "called. Set OPENAI_API_KEY to enable real AI analysis."
                ),
            }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
        except OpenAIError as exc:
            logger.exception("OpenAI API call failed")
            raise AIProviderError(
                f"OpenAI call failed: {exc}", task=task, provider="openai"
            ) from exc
        duration_ms = int((time.monotonic() - start) * 1000)

        usage = response.usage
        log_ai_call(
            task=task or "unknown",
            provider="openai",
            model=model,
            duration_ms=duration_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            prompt_version=prompt_version,
        )

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except ValueError:
            logger.warning("OpenAI returned non-JSON content for a JSON-mode request")
            return {"error": "invalid_json", "raw": content}
