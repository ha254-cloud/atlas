import json
import logging
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.claim_analysis import ClaimAnalysisResult
from app.services.ai.analysis_service import AIAnalysisService
from app.services.ai.prompts.claim_analysis import build_claim_analysis_prompt

VALID_RESULT = {
    "risk_score": 82,
    "recovery_probability": 0.74,
    "priority": "high",
    "confidence": 0.91,
    "recommended_action": "Submit corrected coding with supporting records.",
    "summary": "The denial appears recoverable after a coding correction.",
    "required_documents": ["operative_report", "medical_notes"],
}


class StubContextBuilder:
    def __init__(self, context):
        self.context = context
        self.claims = []

    def build(self, claim):
        self.claims.append(claim)
        return self.context


class StubGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def model_for(self, task):
        return "test-model"

    async def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_prompt_builder_returns_openai_messages_with_serialized_context():
    context = {"claim_number": "CLM-1", "claim_amount": 125.5}

    messages = build_claim_analysis_prompt(context)

    assert [message["role"] for message in messages] == ["system", "user"]
    assert json.loads(messages[1]["content"]) == context
    assert "risk_score" in messages[0]["content"]


@pytest.mark.asyncio
async def test_analyze_builds_context_and_returns_validated_result(caplog):
    claim = SimpleNamespace(id=42)
    context = {"claim_number": "PRIVATE-CLAIM-NUMBER"}
    context_builder = StubContextBuilder(context)
    gateway = StubGateway([VALID_RESULT])
    service = AIAnalysisService(ai_gateway=gateway, context_builder=context_builder)

    with caplog.at_level(logging.INFO):
        result = await service.analyze(claim)

    assert result == ClaimAnalysisResult(**VALID_RESULT)
    assert context_builder.claims == [claim]
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["task"] == "claim_analysis"
    assert json.loads(gateway.calls[0]["prompt"]) == context
    assert "claim_id=42" in caplog.text
    assert "model=test-model" in caplog.text
    assert "PRIVATE-CLAIM-NUMBER" not in caplog.text


@pytest.mark.asyncio
async def test_analyze_retries_once_after_invalid_output():
    gateway = StubGateway([{"error": "invalid_json"}, VALID_RESULT])
    service = AIAnalysisService(
        ai_gateway=gateway,
        context_builder=StubContextBuilder({"claim_number": "CLM-1"}),
    )

    result = await service.analyze(SimpleNamespace(id=42))

    assert result.risk_score == 82
    assert len(gateway.calls) == 2


@pytest.mark.asyncio
async def test_analyze_raises_validation_error_after_two_invalid_outputs():
    gateway = StubGateway(
        [
            {**VALID_RESULT, "confidence": 1.1},
            {**VALID_RESULT, "priority": "urgent"},
        ]
    )
    service = AIAnalysisService(
        ai_gateway=gateway,
        context_builder=StubContextBuilder({"claim_number": "CLM-1"}),
    )

    with pytest.raises(ValidationError):
        await service.analyze(SimpleNamespace(id=42))

    assert len(gateway.calls) == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("risk_score", 101),
        ("recovery_probability", -0.1),
        ("confidence", 1.1),
        ("priority", "urgent"),
    ],
)
def test_result_schema_rejects_invalid_values(field, value):
    with pytest.raises(ValidationError):
        ClaimAnalysisResult.model_validate({**VALID_RESULT, field: value})
