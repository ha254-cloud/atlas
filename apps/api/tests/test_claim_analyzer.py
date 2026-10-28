"""
Unit tests for ClaimAnalyzer — the AI Claim Recovery Engine's structured
assessment layer. No real OpenAI calls are made: a stub AI engine is injected
so the normalization/clamping logic can be verified deterministically.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.ai.claim_analyzer import FALLBACK_RESULT, ClaimAnalyzer


class StubAIEngine:
    """Returns whatever dict it was constructed with, ignoring the prompt
    (unless a test wants to inspect it, via `last_prompt`)."""

    def __init__(self, response: dict):
        self._response = response
        self.last_prompt = None

    async def generate_json(self, prompt, system=None):
        self.last_prompt = prompt
        return self._response


def make_claim():
    return SimpleNamespace(
        claim_number="CLM-1",
        status="denied",
        billed_amount=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 1, 1),
    )


@pytest.mark.asyncio
async def test_analyze_returns_well_formed_result_from_a_valid_response():
    engine = StubAIEngine(
        {
            "denial_cause": "missing_modifier",
            "confidence": 0.9,
            "recovery_probability": 0.75,
            "explanation": "The modifier was omitted on line 1.",
            "recommended_corrections": ["Add modifier 25", "Resubmit claim"],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert result["denial_cause"] == "missing_modifier"
    assert result["confidence"] == 0.9
    assert result["recovery_probability"] == 0.75
    assert result["recommended_corrections"] == ["Add modifier 25", "Resubmit claim"]


@pytest.mark.asyncio
async def test_analyze_falls_back_when_provider_reports_unavailable():
    engine = StubAIEngine({"error": "ai_unavailable", "detail": "no key configured"})
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert result["denial_cause"] == FALLBACK_RESULT["denial_cause"]
    assert result["recovery_probability"] == 0.0
    assert result["explanation"] == "no key configured"


@pytest.mark.asyncio
async def test_analyze_clamps_out_of_range_probabilities():
    engine = StubAIEngine(
        {
            "denial_cause": "coding_error",
            "confidence": 5,
            "recovery_probability": -0.3,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert result["confidence"] == 1.0
    assert result["recovery_probability"] == 0.0


@pytest.mark.asyncio
async def test_analyze_defaults_missing_keys_and_bad_types():
    engine = StubAIEngine({"denial_cause": "eligibility"})
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert result["denial_cause"] == "eligibility"
    assert result["confidence"] == 0.0
    assert result["recovery_probability"] == 0.0
    assert result["recommended_corrections"] == []


@pytest.mark.asyncio
async def test_analyze_coerces_non_list_recommended_corrections():
    engine = StubAIEngine(
        {
            "denial_cause": "other",
            "confidence": 0.5,
            "recovery_probability": 0.5,
            "explanation": "x",
            "recommended_corrections": "not a list",
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert result["recommended_corrections"] == []


@pytest.mark.asyncio
async def test_analyze_grounds_prompt_in_denial_knowledge_base_when_provided():
    engine = StubAIEngine(
        {
            "denial_cause": "timely_filing",
            "confidence": 0.8,
            "recovery_probability": 0.6,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)
    denial_code_info = {
        "code": "CO29",
        "category": "timely_filing",
        "description": "The time limit for filing this claim has expired.",
        "recovery_strategy": "Appeal immediately with proof of timely submission.",
        "severity": "high",
        "recoverability": "low",
        "typical_recovery_rate": 25.0,
        "required_documents": ["Clearinghouse acceptance report"],
        "typical_resolution_days": 30,
        "common_payers": ["Medicare", "Cigna"],
    }

    await analyzer.analyze(make_claim(), denial_code_info)

    assert "CO29" in engine.last_prompt
    assert "Appeal immediately with proof of timely submission." in engine.last_prompt
    assert "Severity: high" in engine.last_prompt
    assert "Recoverability: low" in engine.last_prompt
    assert "Typical Recovery Rate: 25.0%" in engine.last_prompt
    assert "Clearinghouse acceptance report" in engine.last_prompt
    assert "Typical Resolution Time: 30 days" in engine.last_prompt
    assert "Common Payers: Medicare, Cigna" in engine.last_prompt


@pytest.mark.asyncio
async def test_analyze_prompt_has_no_knowledge_base_section_when_not_provided():
    engine = StubAIEngine(
        {
            "denial_cause": "other",
            "confidence": 0.5,
            "recovery_probability": 0.5,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    await analyzer.analyze(make_claim())

    assert "denial knowledge base" not in engine.last_prompt.lower()


class SequenceAIEngine:
    """Returns a different response on each successive call — used to test
    the retry-then-flag-for-review behavior."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.call_count = 0
        self.last_prompt = None

    async def generate_json(self, prompt, system=None):
        self.last_prompt = prompt
        response = self._responses[min(self.call_count, len(self._responses) - 1)]
        self.call_count += 1
        return response


@pytest.mark.asyncio
async def test_analyze_retries_once_on_invalid_response_and_succeeds():
    engine = SequenceAIEngine(
        [
            {"error": "rate_limited"},
            {
                "denial_cause": "coding_error",
                "confidence": 0.8,
                "recovery_probability": 0.6,
                "explanation": "Recovered on retry.",
                "recommended_corrections": [],
            },
        ]
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert engine.call_count == 2
    assert result["denial_cause"] == "coding_error"
    assert "needs_review" not in result


@pytest.mark.asyncio
async def test_analyze_flags_needs_review_when_still_invalid_after_retry():
    engine = SequenceAIEngine([{"denial_cause": "unknown"}])  # missing keys, every call

    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert engine.call_count == 2  # original attempt + one retry
    assert result["needs_review"] is True


@pytest.mark.asyncio
async def test_analyze_does_not_retry_on_a_valid_response():
    engine = StubAIEngine(
        {
            "denial_cause": "eligibility",
            "confidence": 0.9,
            "recovery_probability": 0.8,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    result = await analyzer.analyze(make_claim())

    assert "needs_review" not in result


@pytest.mark.asyncio
async def test_analyze_includes_extra_context_in_prompt_when_provided():
    engine = StubAIEngine(
        {
            "denial_cause": "eligibility",
            "confidence": 0.9,
            "recovery_probability": 0.8,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)
    extra_context = {
        "payer_name": "Aetna",
        "diagnosis_codes": ["M54.5", "R51"],
        "procedure_codes": ["99213"],
        "patient_age": 42,
        "previous_denials": 3,
        "denial_reason": "Missing modifier on original submission.",
    }

    await analyzer.analyze(make_claim(), extra_context=extra_context)

    assert "Payer: Aetna" in engine.last_prompt
    assert "Diagnosis Codes: M54.5, R51" in engine.last_prompt
    assert "Procedure Codes: 99213" in engine.last_prompt
    assert "Patient Age: 42" in engine.last_prompt
    assert "Previous Denials for This Patient: 3" in engine.last_prompt
    assert "Missing modifier on original submission." in engine.last_prompt


@pytest.mark.asyncio
async def test_analyze_prompt_has_no_additional_context_section_when_not_provided():
    engine = StubAIEngine(
        {
            "denial_cause": "eligibility",
            "confidence": 0.9,
            "recovery_probability": 0.8,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    analyzer = ClaimAnalyzer(ai_engine=engine)

    await analyzer.analyze(make_claim())

    assert "Additional Context" not in engine.last_prompt
