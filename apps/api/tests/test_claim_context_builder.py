from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.models.claim_event import ClaimEventType
from app.models.denial import DenialType
from app.models.document import DocumentType
from app.services.ai.context_builder import ClaimContextBuilder


def test_build_normalizes_loaded_claim_context():
    claim = SimpleNamespace(
        claim_number="CLM-100",
        billed_amount=Decimal("1250.50"),
        paid_amount=Decimal("250.00"),
        status="denied",
        service_date=date(2026, 7, 20),
        authorization_number="AUTH-7",
        authorization_expiration=date(2026, 8, 31),
        diagnoses=[
            SimpleNamespace(icd_code="M54.5"),
            SimpleNamespace(icd_code="G89.29"),
        ],
        claim_lines=[
            SimpleNamespace(cpt_code="99213"),
            SimpleNamespace(cpt_code="99213"),
            SimpleNamespace(cpt_code="72100"),
        ],
        patient=SimpleNamespace(
            first_name="Amina",
            last_name="Otieno",
            date_of_birth=date(1986, 7, 21),
        ),
        payer=SimpleNamespace(name="Health Plan One"),
        organization=SimpleNamespace(name="Atlas Medical Group"),
        denials=[
            SimpleNamespace(
                id=1,
                denial_code="CO-16",
                denial_type=DenialType.DOCUMENTATION,
                description="Missing clinical documentation",
                created_at=datetime(2026, 7, 25, tzinfo=UTC),
            )
        ],
        appeals=[],
        claim_events=[
            SimpleNamespace(
                event_type=ClaimEventType.DENIAL_RECORDED,
                description="Denial recorded",
                event_metadata={"code": "CO-16"},
                occurred_at=datetime(2026, 7, 25, tzinfo=UTC),
            )
        ],
        documents=[
            SimpleNamespace(
                document_type=DocumentType.OPERATIVE_REPORT,
                filename="operative-report.pdf",
                extracted_text="Procedure findings",
                ai_summary=None,
            ),
            SimpleNamespace(
                document_type=DocumentType.AUTHORIZATION,
                filename="authorization.pdf",
                extracted_text=None,
                ai_summary="Approved service",
            ),
            SimpleNamespace(
                document_type=DocumentType.PHYSICIAN_NOTES,
                filename="notes.pdf",
                extracted_text="Follow-up notes",
                ai_summary=None,
            ),
        ],
    )

    context = ClaimContextBuilder().build(claim)

    assert context["claim_amount"] == 1250.5
    assert context["diagnosis_codes"] == ["M54.5", "G89.29"]
    assert context["procedure_codes"] == ["99213", "72100"]
    assert context["denial_reason"] == "Missing clinical documentation"
    assert context["patient_name"] == "Amina Otieno"
    assert context["patient_age"] == 39
    assert context["payer_name"] == "Health Plan One"
    assert context["organization_name"] == "Atlas Medical Group"
    assert context["previous_denials"][0]["type"] == "documentation"
    assert context["claim_events"][0]["event_type"] == "claim.denial_recorded"
    assert context["operative_report"][0]["filename"] == "operative-report.pdf"
    assert context["authorization"]["number"] == "AUTH-7"
    assert context["medical_notes"][0]["extracted_text"] == "Follow-up notes"


def test_build_uses_stable_empty_values_for_unmodeled_optional_context():
    claim = SimpleNamespace(
        claim_number="CLM-101",
        billed_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        status="submitted",
        service_date=date(2026, 7, 20),
        authorization_number=None,
        authorization_expiration=None,
        diagnoses=[],
        claim_lines=[],
        patient=None,
        payer=None,
        denials=[],
        documents=[],
    )

    context = ClaimContextBuilder().build(claim)

    assert context["patient_name"] is None
    assert context["gender"] is None
    assert context["plan"] is None
    assert context["policy_number"] is None
    assert context["organization_name"] is None
    assert context["previous_appeals"] == []
    assert context["claim_events"] == []
    assert context["operative_report"] == []
    assert context["authorization"]["documents"] == []
    assert context["medical_notes"] == []
