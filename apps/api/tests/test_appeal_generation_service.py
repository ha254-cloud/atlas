from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.services.ai.appeal_context_builder import AppealContextBuilder
from app.services.ai.appeal_generation_service import AppealGenerationService

VALID_RESULT = {
    "title": "Request for claim reconsideration",
    "letter": "Please reconsider claim CLM-100 based on the supplied medical record.",
    "confidence": 0.91,
    "required_documents": ["Medical record"],
    "missing_documents": [],
    "references": ["Claim CLM-100"],
}


class FakeGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def model_for(self, task):
        return "gpt-test"

    async def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _claim():
    return SimpleNamespace(
        id=1,
        claim_number="CLM-100",
        status="denied",
        service_date=None,
        billed_amount=1000,
        paid_amount=0,
        diagnoses=[SimpleNamespace(icd_code="M54.5")],
        claim_lines=[SimpleNamespace(cpt_code="99213")],
        denials=[
            SimpleNamespace(
                denial_code="CO-50",
                denial_type="medical_necessity",
                description="Medical necessity not established",
            )
        ],
        analysis=SimpleNamespace(
            analysis_status="completed",
            risk_score=85,
            priority="high",
            confidence_score=0.9,
            recovery_probability=0.8,
            root_cause="Missing medical record",
            recommended_action="Submit evidence",
            ai_summary="Recoverable with documentation",
            required_documents=["Medical record"],
        ),
        patient=SimpleNamespace(
            first_name="Ada",
            last_name="Lovelace",
            medical_record_number="MRN-1",
            date_of_birth=None,
        ),
        payer=SimpleNamespace(name="Test Payer", payer_code="TEST"),
        organization=SimpleNamespace(
            name="Atlas Hospital",
            address="1 Main Street",
            phone="555-0100",
            email="billing@example.com",
        ),
        documents=[
            SimpleNamespace(
                id=10,
                document_type="physician_notes",
                filename="notes.pdf",
                extracted_text="Documented medical necessity.",
                ai_summary=None,
            )
        ],
        appeals=[],
    )


def test_context_builder_combines_all_sources():
    context = AppealContextBuilder().build(_claim())

    assert context["claim"]["claim_number"] == "CLM-100"
    assert context["analysis"]["root_cause"] == "Missing medical record"
    assert context["patient"]["name"] == "Ada Lovelace"
    assert context["payer"]["name"] == "Test Payer"
    assert context["organization"]["name"] == "Atlas Hospital"
    assert context["documents"][0]["filename"] == "notes.pdf"
    assert context["previous_appeals"] == []


@pytest.mark.asyncio
async def test_service_returns_strict_result_through_json_gateway():
    gateway = FakeGateway([VALID_RESULT])
    result = await AppealGenerationService(ai_gateway=gateway).generate(_claim())

    assert result.title == VALID_RESULT["title"]
    assert result.confidence == 0.91
    assert gateway.calls[0]["task"] == "appeal"
    assert "Return JSON only" in gateway.calls[0]["system"]
    assert "CLM-100" in gateway.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_service_retries_one_invalid_response():
    gateway = FakeGateway([{"title": "Incomplete"}, VALID_RESULT])

    result = await AppealGenerationService(ai_gateway=gateway).generate(_claim())

    assert result.letter == VALID_RESULT["letter"]
    assert len(gateway.calls) == 2


@pytest.mark.asyncio
async def test_service_rejects_invalid_response_after_retry():
    gateway = FakeGateway([{"confidence": 2}, {"confidence": 2}])

    with pytest.raises(ValidationError):
        await AppealGenerationService(ai_gateway=gateway).generate(_claim())
