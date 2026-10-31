"""
Tests for the Appeal Generation Engine's review/approval lifecycle,
version snapshotting, and ClaimAnalysis-aware prompt building.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.db.database import Base


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
def claim(db, org_id):
    from datetime import date

    from app.models.claim import Claim
    from app.models.claim_diagnosis import ClaimDiagnosis
    from app.models.claim_line import ClaimLine
    from app.models.patient import Patient
    from app.models.payer import Payer

    patient = Patient(
        organization_id=org_id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-2",
        date_of_birth=date(1990, 1, 1),
    )
    payer = Payer(organization_id=org_id, name="BCBS", payer_code="BCBS")
    db.add_all([patient, payer])
    db.flush()

    claim = Claim(
        organization_id=org_id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-LIFECYCLE-001",
        status="denied",
        billed_amount=Decimal("2000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 1, 10),
    )
    db.add(claim)
    db.flush()

    db.add(
        ClaimLine(
            claim_id=claim.id,
            cpt_code="99213",
            modifier="25",
            charge_amount=Decimal("2000.00"),
            paid_amount=Decimal("0.00"),
        )
    )
    db.add(
        ClaimDiagnosis(
            claim_id=claim.id,
            icd_code="M54.5",
            is_primary=True,
        )
    )
    db.commit()
    db.refresh(claim)
    return claim


@pytest.fixture
def analysis(db, org_id, claim):
    from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis

    row = ClaimAnalysis(
        organization_id=org_id,
        claim_id=claim.id,
        analysis_status=AnalysisStatus.COMPLETED,
        denial_category="prior_authorization",
        root_cause="Missing prior authorization number",
        recovery_probability=Decimal("70.00"),
        estimated_recovery_amount=Decimal("1400.00"),
        recommended_action="Submit the retroactive prior auth approval",
        confidence_score=Decimal("90.00"),
        ai_summary="This claim was denied for lack of prior authorization.",
        model_version="gpt-test",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_appeal(db, org_id, claim):
    from app.appeals.service import AppealService

    service = AppealService(db, org_id)
    appeal = service._persist_appeal(
        claim.id,
        None,
        {"appeal_letter": "Dear payer, please reconsider claim " + claim.claim_number},
    )
    return service, appeal


def test_persist_appeal_creates_initial_version(db, org_id, claim):
    from app.models.appeal_version import AppealVersion

    service, appeal = _make_appeal(db, org_id, claim)

    versions = db.query(AppealVersion).filter(AppealVersion.appeal_id == appeal.id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert versions[0].appeal_text == appeal.appeal_text
    assert appeal.current_version == 1


def test_update_appeal_text_snapshots_prior_version(db, org_id, claim):
    from app.models.appeal_version import AppealVersion

    service, appeal = _make_appeal(db, org_id, claim)
    original_text = appeal.appeal_text

    updated = service.update_appeal_text(appeal.id, "Revised appeal text", edited_by=42)

    assert updated.appeal_text == "Revised appeal text"
    assert updated.current_version == 2
    assert updated.generated_by == "42"

    versions = (
        db.query(AppealVersion)
        .filter(AppealVersion.appeal_id == appeal.id)
        .order_by(AppealVersion.version_number)
        .all()
    )
    assert [v.version_number for v in versions] == [1]
    assert versions[0].appeal_text == original_text


def test_update_appeal_text_persists_sections_during_review(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)
    service.submit_for_review(appeal.id)

    sections = {"introduction": "Reviewed introduction"}
    updated = service.update_appeal_text(
        appeal.id,
        "Reviewed appeal text",
        edited_by=42,
        sections=sections,
    )
    db.commit()

    assert updated.status.value == "review"
    assert updated.appeal_text == "Reviewed appeal text"
    assert updated.sections == sections
    assert updated.current_version == 2


def test_update_appeal_text_rejects_changes_after_approval(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)
    original_text = appeal.appeal_text
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id, actor_id=1)

    with pytest.raises(ValueError, match="only draft or in-review"):
        service.update_appeal_text(appeal.id, "Post-approval edit", edited_by=42)

    db.refresh(appeal)
    assert appeal.appeal_text == original_text
    assert appeal.current_version == 1


def test_review_approve_submit_lifecycle(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)

    reviewed = service.submit_for_review(appeal.id)
    assert reviewed.status.value == "review"

    approved = service.approve_appeal(appeal.id, actor_id=1)
    assert approved.status.value == "approved"

    submitted = service.submit_appeal(appeal.id, submitted_by=1, confirmation_number="CONF-999")
    assert submitted.status.value == "submitted"
    assert submitted.confirmation_number == "CONF-999"
    assert submitted.submitted_by == 1


def test_reject_transition(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)
    service.submit_for_review(appeal.id)

    rejected = service.reject_appeal(appeal.id, actor_id=1)
    assert rejected.status.value == "rejected"


def test_cannot_skip_review_before_approval(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)

    with pytest.raises(ValueError):
        service.approve_appeal(appeal.id)


def test_cannot_submit_without_approval(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)

    with pytest.raises(ValueError):
        service.submit_appeal(appeal.id)


def test_manual_submission_requires_confirmation(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id, actor_id=1)

    with pytest.raises(ValueError, match="confirmation or tracking reference"):
        service.submit_appeal(appeal.id, submitted_by=1)


def test_appeal_generator_prompt_includes_analysis_and_real_codes(claim, analysis):
    from app.appeals.generator import AppealGenerator

    prompt = AppealGenerator()._build_prompt(claim, None, analysis)

    assert "M54.5" in prompt
    assert "99213" in prompt
    assert "Missing prior authorization number" in prompt
    assert "Submit the retroactive prior auth approval" in prompt


def test_sectioned_generator_context_uses_real_codes_not_placeholders(claim, analysis):
    from app.appeals.sectioned_generator import SectionedAppealGenerator

    context = SectionedAppealGenerator()._build_context(claim, None, analysis)

    assert context["diagnosis_codes"] == "M54.5"
    assert context["procedure_codes"] == "99213"
    assert context["modifiers"] == "25"
    assert context["root_cause"] == "Missing prior authorization number"
    assert context["recommended_action"] == "Submit the retroactive prior auth approval"


def test_appeal_generator_prompt_includes_patient_and_payer_and_hospital_names(claim):
    from app.appeals.generator import AppealGenerator
    from app.models.organization import Organization

    org = Organization(id=1, name="Nairobi General Hospital")
    prompt = AppealGenerator()._build_prompt(claim, None, None, org)

    assert "Jane Doe" in prompt
    assert "BCBS" in prompt
    assert "Nairobi General Hospital" in prompt
    # Regression guard: the prompt used to leak a raw payer_id instead of
    # the real payer name.
    assert "payer_id=" not in prompt


def test_appeal_generator_prompt_falls_back_gracefully_without_organization(claim):
    from app.appeals.generator import AppealGenerator

    prompt = AppealGenerator()._build_prompt(claim, None, None, None)

    assert "the provider organization" in prompt


def test_appeal_generator_prompt_requires_verified_kenya_sources(claim):
    from app.ai.prompt_loader import load_prompt
    from app.appeals.generator import AppealGenerator

    prompt = AppealGenerator()._build_prompt(claim, None)
    system = load_prompt("appeal")

    assert "Billed Amount (KES)" in prompt
    assert "return an empty citations list" in prompt
    assert "Never invent a payer policy" in system
    assert "Do not cite CMS, LCD, NCD, CPT, or HCPCS" in system


def test_sectioned_generator_context_includes_patient_and_payer_and_hospital_names(claim):
    from app.appeals.sectioned_generator import SectionedAppealGenerator
    from app.models.organization import Organization

    org = Organization(id=1, name="Nairobi General Hospital")
    context = SectionedAppealGenerator()._build_context(claim, None, None, org)

    assert context["patient_name"] == "Jane Doe"
    assert context["payer_name"] == "BCBS"
    assert context["hospital_name"] == "Nairobi General Hospital"


@pytest.mark.asyncio
async def test_sectioned_generator_uses_one_grounded_json_call(claim, analysis, monkeypatch):
    from app.ai.gateway import gateway
    from app.appeals.sectioned_generator import SECTIONS, SectionedAppealGenerator

    calls = []
    sections = {
        "introduction": (
            "We request reconsideration of claim CLM-LIFECYCLE-001 for patient Jane Doe."
        ),
        "medical_necessity": "The documented diagnosis M54.5 supports review of the service.",
        "coding_justification": "Procedure 99213 with modifier 25 should be reviewed.",
        "policy_references": "Payer policy verification is required before submission.",
        "supporting_documents": "No supporting documents are represented as attached.",
        "requested_action": "Please reconsider and reprocess the claim.",
        "signature": "Sincerely,\nAuthorized Provider Representative",
    }

    async def fake_generate_json(task, prompt, system=None, *, cache_key=None):
        calls.append({"task": task, "prompt": prompt, "system": system})
        return {
            "title": "Claim reconsideration",
            "summary": "Grounded appeal draft",
            "sections": sections,
            "key_arguments": ["Review the documented coding"],
            "citations": [],
            "attachments": [],
            "missing_information": ["Verified payer policy"],
            "confidence": 82,
        }

    monkeypatch.setattr(gateway, "generate_json", fake_generate_json)

    result = await SectionedAppealGenerator().generate(claim, analysis=analysis)

    assert len(calls) == 1
    assert calls[0]["task"] == "appeal_sectioned"
    assert "Never invent clinical facts" in calls[0]["system"]
    assert "M54.5" in calls[0]["prompt"]
    assert set(result["sections"]) == set(SECTIONS)
    assert result["confidence"] == 82
    assert "CLM-LIFECYCLE-001" in result["appeal_letter"]
    assert "Jane Doe" in result["appeal_letter"]


def test_evidence_collector_flags_documents_it_cannot_verify(claim):
    from app.appeals.evidence import EvidenceCollector

    denial_code_info = {"required_documents": ["Operative report", "Physician notes"]}
    result = EvidenceCollector().check(claim, denial_code_info)

    assert result.needs_verification == ["Operative report", "Physician notes"]
    assert result.verified == []
    assert not result.is_complete


def test_evidence_collector_verifies_documents_atlas_can_corroborate(claim):
    from app.appeals.evidence import EvidenceCollector

    claim.authorization_number = "AUTH-123"
    denial_code_info = {
        "required_documents": [
            "Prior authorization approval",
            "Diagnosis documentation",
            "Operative report",
        ],
    }
    result = EvidenceCollector().check(claim, denial_code_info)

    assert "Prior authorization approval" in result.verified
    assert "Diagnosis documentation" in result.verified
    assert result.needs_verification == ["Operative report"]


def test_evidence_collector_handles_no_denial_code_info(claim):
    from app.appeals.evidence import EvidenceCollector

    result = EvidenceCollector().check(claim, None)

    assert result.required == []
    assert result.is_complete


def test_validate_appeal_rejects_missing_denial_code_reference():
    from app.appeals.validator import AppealValidationError, validate_appeal

    data = {
        "appeal_letter": "Dear payer, please reconsider claim CLM-1. " + ("Padding text. " * 20)
    }
    with pytest.raises(AppealValidationError):
        validate_appeal(data, "CLM-1", denial_code="CO-16")


def test_validate_appeal_accepts_denial_code_regardless_of_hyphenation():
    from app.appeals.validator import validate_appeal

    data = {
        "appeal_letter": (
            "Dear payer, please reconsider claim CLM-1, denied under code CO16, "
            "for patient Doe. " + ("Padding text. " * 20)
        )
    }
    # Should not raise even though the letter says "CO16" and the stored
    # code is "CO-16" (loose/normalized comparison).
    validate_appeal(data, "CLM-1", denial_code="CO-16", patient_last_name="Doe")


def test_validate_appeal_rejects_missing_patient_name():
    from app.appeals.validator import AppealValidationError, validate_appeal

    data = {
        "appeal_letter": "Dear payer, please reconsider claim CLM-1. " + ("Padding text. " * 20)
    }
    with pytest.raises(AppealValidationError):
        validate_appeal(data, "CLM-1", patient_last_name="Doe")


def test_validate_sections_rejects_too_short_section():
    from app.appeals.validator import AppealValidationError, validate_sections

    with pytest.raises(AppealValidationError):
        validate_sections({"introduction": "Hi"}, required=["introduction"])


def test_validate_sections_rejects_unfilled_template_artifact():
    from app.appeals.validator import AppealValidationError, validate_sections

    sections = {"introduction": "This appeal concerns claim {claim_number} and needs review."}
    with pytest.raises(AppealValidationError):
        validate_sections(sections, required=["introduction"])


def test_validate_sections_passes_when_complete():
    from app.appeals.validator import validate_sections

    sections = {"introduction": "This appeal concerns claim CLM-1 and requests reconsideration."}
    validate_sections(sections, required=["introduction"])  # should not raise
