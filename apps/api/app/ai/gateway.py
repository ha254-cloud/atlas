"""
AI Gateway — routes requests to the correct provider based on task type.

Different tasks suit different models:
  - Appeal generation  → GPT-4  (only provider with a real integration for now — see local-dev-notes)
  - Denial analysis    → GPT-4   (fast, reliable classification)
  - Code validation    → GPT-4   (structured JSON output)
  - Large summaries    → Gemini  (long context window)
  - Offline / local    → Ollama  (no external dependency)

The gateway reads routing config from settings so it can be overridden
per environment without code changes.
"""

import logging

from app.ai.cache import get_cached_json, set_cached_json
from app.ai.cost_tracking import log_ai_call
from app.ai.exceptions import AIProviderError
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai import OpenAIProvider
from app.core.config import settings

logger = logging.getLogger(__name__)

# Task → preferred provider name.
# NOTE: "documentation" intentionally routes to "openai", not "gemini" —
# GeminiProvider is still a stub (see providers/gemini.py), so routing a
# real feature (document summarization, app/documents/service.py) to it
# would silently return canned placeholder text instead of a real summary.
# Route to a stub-backed task only if you're OK with that placeholder
# behavior for now.
_TASK_ROUTING: dict[str, str] = {
    "appeal": "openai",
    "claim_analysis": "openai",
    "denial": "openai",
    "coding": "openai",
    "recovery": "openai",
    "eligibility": "openai",
    "medical_necessity": "anthropic",
    "documentation": "openai",
    "document_classification": "openai",
    "underpayment": "openai",
}

# Task → model. Higher-stakes generation tasks (drafting appeal text that
# a human reviews and submits) use the primary/quality model; high-volume
# classification-style tasks use the cheaper/faster model. Only meaningful
# for providers that support per-call model overrides (currently OpenAI
# only) — other providers ignore the `model` kwarg entirely.
_TASK_MODEL: dict[str, str] = {
    "appeal": settings.AI_MODEL,
    "medical_necessity": settings.AI_MODEL,
    "claim_analysis": settings.AI_MODEL_FAST,
    "denial": settings.AI_MODEL_FAST,
    "coding": settings.AI_MODEL_FAST,
    "recovery": settings.AI_MODEL_FAST,
    "eligibility": settings.AI_MODEL_FAST,
    "documentation": settings.AI_MODEL_FAST,
    "document_classification": settings.AI_MODEL_FAST,
    "underpayment": settings.AI_MODEL_FAST,
}

# Prompt version per task — bump when a prompt template's wording changes
# meaningfully enough that you'd want to distinguish analyses produced
# under the old vs. new prompt. Recorded on every AICallLog row; not yet
# wired to automatically reload a specific prompt version's file (there's
# only ever "the current file on disk"), it's a manual audit trail today.
_PROMPT_VERSIONS: dict[str, str] = {
    "appeal": "1.0",
    "claim_analysis": "1.0",
    "denial": "1.0",
    "coding": "1.0",
    "recovery": "1.0",
    "eligibility": "1.0",
    "medical_necessity": "1.0",
    "documentation": "1.0",
    "document_classification": "1.0",
    "underpayment": "1.0",
}


class AIGateway:
    """
    Single entry point for all AI generation.
    Callers specify a task name; the gateway picks the right provider,
    model, and prompt version, and every call is logged (see
    app/ai/cost_tracking.py) for usage/cost visibility.
    Fallback chain: task provider → default provider → OpenAI.
    """

    def __init__(self):
        self._providers: dict[str, AIProvider] = {
            "openai": OpenAIProvider(),
            "anthropic": AnthropicProvider(),
            "gemini": GeminiProvider(),
            "ollama": OllamaProvider(),
        }

    def provider_for(self, task: str) -> AIProvider:
        name = _TASK_ROUTING.get(task, settings.AI_PROVIDER)
        return self._providers.get(name, self._providers["openai"])

    def provider_name_for(self, task: str) -> str:
        name = _TASK_ROUTING.get(task, settings.AI_PROVIDER)
        return name if name in self._providers else "openai"

    def model_for(self, task: str) -> str:
        return _TASK_MODEL.get(task, settings.AI_MODEL)

    def prompt_version_for(self, task: str) -> str:
        return _PROMPT_VERSIONS.get(task, "1.0")

    async def generate(
        self,
        task: str,
        prompt: str,
        system: str | None = None,
        *,
        cache_key: str | None = None,
    ) -> str:
        """
        `cache_key`, if supplied (see app/ai/cache.py::build_cache_key), is
        checked in Redis before calling the provider and populated after a
        successful call — callers that don't pass one simply skip caching
        entirely (existing behavior, unchanged).
        """
        if not prompt or not prompt.strip():
            raise ValueError(
                f"Refusing to call the AI gateway with an empty prompt (task={task!r})"
            )

        if cache_key is not None:
            cached = get_cached_json(cache_key)
            if cached is not None and "text" in cached:
                log_ai_call(
                    task=task,
                    provider=self.provider_name_for(task),
                    model=self.model_for(task),
                    duration_ms=0,
                    cache_hit=True,
                    prompt_version=self.prompt_version_for(task),
                )
                return cached["text"]

        provider = self.provider_for(task)
        try:
            result = await provider.generate(
                prompt=prompt,
                system=system,
                task=task,
                model=self.model_for(task),
                prompt_version=self.prompt_version_for(task),
            )
        except AIProviderError:
            raise
        except Exception as exc:
            logger.exception("AI provider call failed for task=%s", task)
            raise AIProviderError(
                f"AI provider call failed: {exc}", task=task, provider=self.provider_name_for(task)
            ) from exc

        if cache_key is not None:
            set_cached_json(cache_key, {"text": result})

        return result

    async def generate_json(
        self,
        task: str,
        prompt: str,
        system: str | None = None,
        *,
        cache_key: str | None = None,
    ) -> dict:
        """
        Same as generate(), but for tasks that need structured JSON output
        (parsed and validated by the caller) instead of freeform text.
        Only providers that implement `generate_json` (currently OpenAI)
        can serve tasks routed to them via this method.

        `cache_key` works the same way as in generate() — skip entirely if
        not supplied. Error-shaped responses (`{"error": ...}`, e.g. when
        the provider is unavailable or returned unparseable JSON) are
        deliberately never cached, so a transient failure doesn't get
        "stuck" as the cached answer until the claim is next edited.
        """
        if not prompt or not prompt.strip():
            raise ValueError(
                f"Refusing to call the AI gateway with an empty prompt (task={task!r})"
            )

        if cache_key is not None:
            cached = get_cached_json(cache_key)
            if cached is not None and "error" not in cached:
                log_ai_call(
                    task=task,
                    provider=self.provider_name_for(task),
                    model=self.model_for(task),
                    duration_ms=0,
                    cache_hit=True,
                    prompt_version=self.prompt_version_for(task),
                )
                return cached

        provider = self.provider_for(task)
        try:
            result = await provider.generate_json(
                prompt=prompt,
                system=system,
                task=task,
                model=self.model_for(task),
                prompt_version=self.prompt_version_for(task),
            )
        except AIProviderError:
            raise
        except Exception as exc:
            logger.exception("AI provider call failed for task=%s", task)
            raise AIProviderError(
                f"AI provider call failed: {exc}", task=task, provider=self.provider_name_for(task)
            ) from exc

        if cache_key is not None and isinstance(result, dict) and "error" not in result:
            set_cached_json(cache_key, result)

        return result


# Module-level singleton
gateway = AIGateway()
