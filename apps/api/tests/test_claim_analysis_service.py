"""
Tests for ClaimAnalysisService — the single entry point for AI claim
analysis (Recovery Intelligence Engine). Verifies it persists a structured
ClaimAnalysis row, maps the AI's predicted denial cause onto the
standardized DenialType on the claim's Denial record, writes the AI-derived
scores back onto the Claim, re-scores the RecoveryCase, and records an
ANALYZED timeline event — all via an injected stub AI engine (no real
OpenAI calls).
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.db.database import Base


class StubAIEngine:
    def __init__(self, response: dict):
        self._response = response
        self.last_prompt = None

    async def generate_json(self, prompt, system=None):
        self.last_prompt = prompt
        return self._response


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def org_id():
    return 1


@pytest.fixture
def seeded_claim(db, org_id):
    from app.models.claim import Claim
    from app.models.denial import Denial, DenialType
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.recovery_case import RecoveryCase, RecoveryStatus

    patient = Patient(
        organization_id=org_id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-1",
        date_of_birth=date(1990, 1, 1),
    )
    payer = Payer(organization_id=org_id, name="BCBS", payer_code="BCBS")
    db.add_all([patient, payer])
    db.flush()

    claim = Claim(
        organization_id=org_id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-ANALYSIS-001",
        status="denied",
        billed_amount=Decimal("2000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 1, 10),
    )
    db.add(claim)
    db.flush()

    denial = Denial(
        organization_id=org_id,
        claim_id=claim.id,
        denial_code="CO-197",
        denial_type=DenialType.OTHER,
        description="Missing prior authorization.",
    )
    recovery_case = RecoveryCase(
        organization_id=org_id,
        claim_id=claim.id,
        recovery_score=Decimal("50.00"),
        estimated_value=Decimal("1000.00"),
        status=RecoveryStatus.OPEN,
        recommendation="Review claim and pursue recovery",
    )
    db.add_all([denial, recovery_case])
    db.commit()
    db.refresh(claim)
    return claim


@pytest.mark.asyncio
async def test_analyze_and_store_creates_structured_analysis_and_classifies_denial(
    db, org_id, seeded_claim
):
    from app.models.claim_analysis import AnalysisStatus
    from app.models.denial import Denial, DenialType
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "prior_authorization",
            "confidence": 0.85,
            "recovery_probability": 0.3,
            "explanation": "Missing prior authorization documentation.",
            "recommended_corrections": ["Attach authorization record", "Resubmit claim"],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    analysis = await service.analyze_and_store(seeded_claim)

    assert analysis.analysis_status == AnalysisStatus.COMPLETED
    assert analysis.denial_category == DenialType.PRIOR_AUTH.value
    assert analysis.root_cause == "prior_authorization"
    assert analysis.recovery_probability == Decimal("30.00")
    assert analysis.estimated_recovery_amount == Decimal("600.00")  # 2000 balance * 0.30
    assert "Attach authorization record" in analysis.recommended_action
    assert analysis.confidence_score == Decimal("85.00")
    assert analysis.ai_summary == "Missing prior authorization documentation."
    assert analysis.model_version == "gpt-4.1"

    denial = db.query(Denial).filter(Denial.claim_id == seeded_claim.id).first()
    assert denial.denial_type == DenialType.PRIOR_AUTH

    db.refresh(seeded_claim)
    assert seeded_claim.recovery_probability == Decimal("30.00")
    assert seeded_claim.ai_risk_score == Decimal("70.00")


@pytest.mark.asyncio
async def test_analyze_and_store_records_analyzed_timeline_event(db, org_id, seeded_claim):
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "coding_error",
            "confidence": 0.6,
            "recovery_probability": 0.4,
            "explanation": "Incorrect CPT code used.",
            "recommended_corrections": ["Correct CPT code"],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    event = (
        db.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == seeded_claim.id, ClaimEvent.event_type == ClaimEventType.ANALYZED
        )
        .first()
    )
    assert event is not None


@pytest.mark.asyncio
async def test_analyze_and_store_rescores_recovery_case(db, org_id, seeded_claim):
    from app.models.recovery_case import RecoveryCase
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "eligibility",
            "confidence": 0.7,
            "recovery_probability": 0.9,
            "explanation": "Patient was eligible at time of service.",
            "recommended_corrections": ["Resubmit with eligibility proof"],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    recovery_case = db.query(RecoveryCase).filter(RecoveryCase.claim_id == seeded_claim.id).first()
    # Original placeholder was created with denial_probability=0.5; a real
    # 0.9 probability on a $2000 balance should score meaningfully higher.
    assert recovery_case.recovery_score > Decimal("50.00")


@pytest.mark.asyncio
async def test_analyze_and_store_does_not_raise_when_auto_appeal_fails(db, org_id, seeded_claim):
    """Auto-drafting an appeal is best-effort — a failure there (e.g. the AI
    provider being unavailable/unconfigured) must not blow up analysis."""
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "duplicate_claim",
            "confidence": 0.8,
            "recovery_probability": 0.95,
            "explanation": "High confidence recovery case.",
            "recommended_corrections": ["Resubmit"],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    analysis = await service.analyze_and_store(seeded_claim)

    assert analysis is not None


@pytest.mark.asyncio
async def test_analyze_and_store_grounds_prompt_in_denial_knowledge_base(db, org_id, seeded_claim):
    """seeded_claim's Denial has denial_code='CO-197' — with a matching
    DenialCode knowledge-base row present, the service should look it up
    and pass its category/description/recovery_strategy into the
    analyzer's prompt as grounding context."""
    from app.models.denial import DenialType
    from app.models.denial_code import DenialCode
    from app.services.claim_analysis_service import ClaimAnalysisService

    db.add(
        DenialCode(
            code="CO197",
            category=DenialType.PRIOR_AUTH,
            description="Precertification/authorization/notification absent.",
            recovery_strategy="Obtain retroactive authorization or appeal with proof.",
        )
    )
    db.commit()

    stub = StubAIEngine(
        {
            "denial_cause": "prior_authorization",
            "confidence": 0.7,
            "recovery_probability": 0.5,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    assert "CO197" in stub.last_prompt
    assert "Obtain retroactive authorization or appeal with proof." in stub.last_prompt


@pytest.mark.asyncio
async def test_analyze_and_store_enriches_prompt_with_payer_diagnosis_procedure_and_patient_age(
    db, org_id, seeded_claim
):
    """Sprint 11: the prompt should include richer claim context beyond the
    bare claim fields — payer name, diagnosis/procedure codes, and patient
    age — sourced from relationships ClaimRepository already eager-loads."""
    from app.models.claim_diagnosis import ClaimDiagnosis
    from app.models.claim_line import ClaimLine
    from app.services.claim_analysis_service import ClaimAnalysisService

    db.add(ClaimDiagnosis(claim_id=seeded_claim.id, icd_code="M54.5", is_primary=True))
    db.add(
        ClaimLine(
            claim_id=seeded_claim.id,
            cpt_code="99213",
            units=1,
            charge_amount=Decimal("200.00"),
        )
    )
    db.commit()
    db.refresh(seeded_claim)

    expected_age = date.today().year - 1990 - ((date.today().month, date.today().day) < (1, 1))

    stub = StubAIEngine(
        {
            "denial_cause": "prior_authorization",
            "confidence": 0.7,
            "recovery_probability": 0.5,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    assert "Payer: BCBS" in stub.last_prompt
    assert "Diagnosis Codes: M54.5" in stub.last_prompt
    assert "Procedure Codes: 99213" in stub.last_prompt
    assert f"Patient Age: {expected_age}" in stub.last_prompt


@pytest.mark.asyncio
async def test_analyze_and_store_counts_previous_denials_for_same_patient(db, org_id, seeded_claim):
    """Sprint 11: previous denials for the same patient (across other
    claims) should be surfaced in the prompt as context."""
    from app.models.claim import Claim
    from app.models.denial import Denial, DenialType
    from app.services.claim_analysis_service import ClaimAnalysisService

    other_claim = Claim(
        organization_id=org_id,
        patient_id=seeded_claim.patient_id,
        payer_id=seeded_claim.payer_id,
        claim_number="CLM-ANALYSIS-002",
        status="denied",
        billed_amount=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2025, 6, 1),
    )
    db.add(other_claim)
    db.flush()
    db.add(
        Denial(
            organization_id=org_id,
            claim_id=other_claim.id,
            denial_code="CO-1",
            denial_type=DenialType.OTHER,
            description="Some other denial.",
        )
    )
    db.commit()
    db.refresh(seeded_claim)

    stub = StubAIEngine(
        {
            "denial_cause": "prior_authorization",
            "confidence": 0.7,
            "recovery_probability": 0.5,
            "explanation": "x",
            "recommended_corrections": [],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    assert "Previous Denials for This Patient: 1" in stub.last_prompt


@pytest.mark.asyncio
async def test_analyze_and_store_records_analysis_started_timeline_event(db, org_id, seeded_claim):
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "coding_error",
            "confidence": 0.6,
            "recovery_probability": 0.4,
            "explanation": "Incorrect CPT code used.",
            "recommended_corrections": ["Correct CPT code"],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    await service.analyze_and_store(seeded_claim)

    event = (
        db.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == seeded_claim.id,
            ClaimEvent.event_type == ClaimEventType.ANALYSIS_STARTED,
        )
        .first()
    )
    assert event is not None


@pytest.mark.asyncio
async def test_analyze_and_store_flags_needs_review_when_ai_response_stays_invalid(
    db, org_id, seeded_claim
):
    """Sprint 11: if the AI response is still invalid after one automatic
    retry, the persisted ClaimAnalysis should be flagged needs_review
    rather than silently look like a normal, trustworthy analysis."""
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine({"denial_cause": "unknown"})  # missing required keys, every attempt
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    analysis = await service.analyze_and_store(seeded_claim)

    assert analysis.needs_review is True


@pytest.mark.asyncio
async def test_analyze_and_store_does_not_flag_needs_review_for_a_valid_response(
    db, org_id, seeded_claim
):
    from app.services.claim_analysis_service import ClaimAnalysisService

    stub = StubAIEngine(
        {
            "denial_cause": "eligibility",
            "confidence": 0.7,
            "recovery_probability": 0.6,
            "explanation": "Looks fine.",
            "recommended_corrections": [],
        }
    )
    service = ClaimAnalysisService(db, org_id, ai_engine=stub)

    analysis = await service.analyze_and_store(seeded_claim)

    assert analysis.needs_review is False
