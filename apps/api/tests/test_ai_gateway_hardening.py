"""
Sprint 7 — Production AI Gateway hardening tests.

Covers the three genuine gaps closed this round (see local-dev-notes for
the full "what already existed vs. what was actually missing" writeup):
  1. AIProviderError — provider/gateway no longer leak SDK-specific
     exception types to callers.
  2. Redis response caching — AIGateway.generate_json()/generate() skip
     the provider entirely on a cache hit, and never cache error-shaped
     responses.
  3. ClaimAnalysisAIResponse — a real Pydantic schema documenting/
     validating ClaimAnalyzer's structured output shape.

No real OpenAI or Redis calls are made anywhere in this file.
"""

from datetime import UTC, datetime

import pytest
from openai import OpenAIError
from pydantic import ValidationError

from app.ai.cache import build_cache_key
from app.ai.claim_analyzer import _validate_shape
from app.ai.cost_tracking import ai_call_context, log_ai_call
from app.ai.exceptions import AIProviderError
from app.ai.gateway import AIGateway
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas import ClaimAnalysisAIResponse


class FakeChatCompletions:
    def __init__(self, *, raise_exc=None, content='{"ok": true}'):
        self._raise_exc = raise_exc
        self._content = content

    async def create(self, **kwargs):
        if self._raise_exc is not None:
            raise self._raise_exc
        return type(
            "Resp",
            (),
            {
                "choices": [
                    type("Choice", (), {"message": type("Msg", (), {"content": self._content})()})()
                ],
                "usage": None,
            },
        )()


class FakeOpenAIClient:
    def __init__(self, **kwargs):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions(**kwargs)})()


class StubProvider:
    """Duck-typed provider double used for AIGateway-level tests."""

    def __init__(self, *, json_result=None, text_result="hi", raise_exc=None):
        self._json_result = json_result if json_result is not None else {}
        self._text_result = text_result
        self._raise_exc = raise_exc
        self.calls = 0

    async def generate(self, prompt, system=None, *, task=None, model=None, prompt_version=None):
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._text_result

    async def generate_json(
        self, prompt, system=None, *, task=None, model=None, prompt_version=None
    ):
        self.calls += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._json_result


class TestAIProviderError:
    @pytest.mark.asyncio
    async def test_generate_wraps_openai_error(self):
        provider = OpenAIProvider()
        provider._client = FakeOpenAIClient(raise_exc=OpenAIError("boom"))

        with pytest.raises(AIProviderError) as exc_info:
            await provider.generate("prompt", task="claim_analysis")

        assert exc_info.value.provider == "openai"
        assert exc_info.value.task == "claim_analysis"

    @pytest.mark.asyncio
    async def test_generate_json_wraps_openai_error(self):
        provider = OpenAIProvider()
        provider._client = FakeOpenAIClient(raise_exc=OpenAIError("boom"))

        with pytest.raises(AIProviderError):
            await provider.generate_json("prompt", task="claim_analysis")

    @pytest.mark.asyncio
    async def test_gateway_wraps_unexpected_provider_exception(self):
        gateway = AIGateway()
        gateway._providers["openai"] = StubProvider(raise_exc=RuntimeError("network blip"))

        with pytest.raises(AIProviderError):
            await gateway.generate_json(task="claim_analysis", prompt="hello")

    @pytest.mark.asyncio
    async def test_gateway_does_not_double_wrap_ai_provider_error(self):
        original = AIProviderError("already wrapped", task="claim_analysis", provider="openai")
        gateway = AIGateway()
        gateway._providers["openai"] = StubProvider(raise_exc=original)

        with pytest.raises(AIProviderError) as exc_info:
            await gateway.generate_json(task="claim_analysis", prompt="hello")

        assert exc_info.value is original


class TestCacheKey:
    def test_build_cache_key_includes_all_components(self):
        updated = datetime(2026, 1, 1, tzinfo=UTC)
        key = build_cache_key(
            task="claim_analysis",
            claim_id=42,
            prompt_version="1.0",
            model="gpt-4.1-mini",
            claim_updated_at=updated,
        )
        assert key == f"ai:cache:claim_analysis:42:1.0:gpt-4.1-mini:{updated.isoformat()}"

    def test_build_cache_key_handles_missing_timestamp(self):
        key = build_cache_key(
            task="claim_analysis",
            claim_id=1,
            prompt_version="1.0",
            model="gpt-4.1-mini",
            claim_updated_at=None,
        )
        assert key.endswith(":unknown")


class TestTenantAttribution:
    def test_unattributed_ai_call_is_not_persisted(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "app.db.database.SessionLocal",
            lambda: pytest.fail("unattributed usage must not open a database session"),
        )

        log_ai_call(
            task="claim_analysis",
            provider="openai",
            model="gpt-4.1-mini",
            duration_ms=10,
        )

        assert "organization context is missing" in caplog.text

    def test_attributed_ai_call_persists_organization(self, monkeypatch):
        persisted = []

        class FakeSession:
            def add(self, row):
                persisted.append(row)

            def commit(self):
                return None

            def close(self):
                return None

        monkeypatch.setattr("app.db.database.SessionLocal", FakeSession)

        with ai_call_context(organization_id=42, claim_id=7):
            log_ai_call(
                task="claim_analysis",
                provider="openai",
                model="gpt-4.1-mini",
                duration_ms=10,
            )

        assert len(persisted) == 1
        assert persisted[0].organization_id == 42
        assert persisted[0].claim_id == 7


class TestGatewayCaching:
    @pytest.mark.asyncio
    async def test_generate_json_enforces_budget_before_provider_call(self, monkeypatch):
        gateway = AIGateway()
        stub = StubProvider(json_result={"denial_cause": "eligibility"})
        gateway._providers["openai"] = stub

        def budget_exceeded(**_kwargs):
            raise AIProviderError(
                "AI monthly budget has been reached",
                task="claim_analysis",
                provider="openai",
            )

        monkeypatch.setattr("app.ai.gateway.enforce_monthly_budget", budget_exceeded)

        with pytest.raises(AIProviderError, match="budget"):
            await gateway.generate_json(task="claim_analysis", prompt="hello")

        assert stub.calls == 0

    @pytest.mark.asyncio
    async def test_generate_json_returns_cached_result_without_calling_provider(self, monkeypatch):
        gateway = AIGateway()
        stub = StubProvider(json_result={"denial_cause": "eligibility"})
        gateway._providers["openai"] = stub

        monkeypatch.setattr(
            "app.ai.gateway.get_cached_json", lambda key: {"denial_cause": "cached"}
        )
        monkeypatch.setattr(
            "app.ai.gateway.set_cached_json",
            lambda *a, **kw: pytest.fail("should not cache on a hit"),
        )

        result = await gateway.generate_json(task="claim_analysis", prompt="hello", cache_key="k1")

        assert result == {"denial_cause": "cached"}
        assert stub.calls == 0

    @pytest.mark.asyncio
    async def test_generate_json_caches_successful_miss(self, monkeypatch):
        gateway = AIGateway()
        stub = StubProvider(json_result={"denial_cause": "eligibility"})
        gateway._providers["openai"] = stub

        stored = {}
        monkeypatch.setattr("app.ai.gateway.get_cached_json", lambda key: None)
        monkeypatch.setattr(
            "app.ai.gateway.set_cached_json",
            lambda key, value, **kw: stored.update({key: value}),
        )

        result = await gateway.generate_json(task="claim_analysis", prompt="hello", cache_key="k2")

        assert result == {"denial_cause": "eligibility"}
        assert stub.calls == 1
        assert stored == {"k2": {"denial_cause": "eligibility"}}

    @pytest.mark.asyncio
    async def test_generate_json_never_caches_error_shaped_result(self, monkeypatch):
        gateway = AIGateway()
        stub = StubProvider(json_result={"error": "ai_unavailable"})
        gateway._providers["openai"] = stub

        monkeypatch.setattr("app.ai.gateway.get_cached_json", lambda key: None)
        monkeypatch.setattr(
            "app.ai.gateway.set_cached_json",
            lambda *a, **kw: pytest.fail("should never cache an error-shaped response"),
        )

        result = await gateway.generate_json(task="claim_analysis", prompt="hello", cache_key="k3")

        assert result == {"error": "ai_unavailable"}

    @pytest.mark.asyncio
    async def test_generate_json_without_cache_key_skips_caching_entirely(self, monkeypatch):
        gateway = AIGateway()
        stub = StubProvider(json_result={"denial_cause": "eligibility"})
        gateway._providers["openai"] = stub

        monkeypatch.setattr(
            "app.ai.gateway.get_cached_json",
            lambda *a, **kw: pytest.fail("should not check cache when no cache_key is given"),
        )

        result = await gateway.generate_json(task="claim_analysis", prompt="hello")

        assert result == {"denial_cause": "eligibility"}
        assert stub.calls == 1


class TestClaimAnalysisSchema:
    def test_schema_accepts_a_valid_normalized_result(self):
        model = ClaimAnalysisAIResponse(
            denial_cause="eligibility",
            confidence=0.8,
            recovery_probability=0.5,
            explanation="x",
            recommended_corrections=["Resubmit"],
        )
        assert model.confidence == 0.8

    def test_schema_rejects_out_of_range_confidence(self):
        with pytest.raises(ValidationError):
            ClaimAnalysisAIResponse(
                denial_cause="eligibility",
                confidence=5.0,
                recovery_probability=0.5,
                explanation="x",
                recommended_corrections=[],
            )

    def test_validate_shape_never_raises_on_malformed_input(self):
        # _validate_shape is log-only — must never raise even on garbage.
        _validate_shape({"denial_cause": "eligibility"})
