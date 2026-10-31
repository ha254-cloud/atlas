"""
Tests for Sprint 12 — AI Appeal Generation enrichment:
  - Citation Engine (KB-grounded citations populated instead of always empty)
  - Missing Documents Detection blocking mode (require_evidence=True)
  - Appeal Quality Score (completeness/evidence/tone/compliance/confidence)
  - Submission Readiness checks (attachments/timely filing/approval)
  - AI Revision regeneration + versioning
  - Appeal Dashboard metrics
"""

import json
from datetime import date, timedelta
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
    from app.models.claim import Claim
    from app.models.patient import Patient
    from app.models.payer import Payer

    patient = Patient(
        organization_id=org_id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-S12",
        date_of_birth=date(1990, 1, 1),
    )
    payer = Payer(organization_id=org_id, name="BCBS", payer_code="BCBS")
    db.add_all([patient, payer])
    db.flush()

    claim = Claim(
        organization_id=org_id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-S12-001",
        status="denied",
        billed_amount=Decimal("1000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date.today() - timedelta(days=30),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


@pytest.fixture
def denial_code_timely_filing(db):
    from app.models.denial import DenialType
    from app.models.denial_code import DenialCode

    code = DenialCode(
        code="CO29",
        category=DenialType.TIMELY_FILING,
        description="Timely filing limit expired",
        recovery_strategy="Appeal with proof of timely submission",
        required_documents=["Proof of timely submission"],
    )
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


@pytest.fixture
def denial(db, org_id, claim, denial_code_timely_filing):
    from app.models.denial import Denial, DenialType

    d = Denial(
        organization_id=org_id,
        claim_id=claim.id,
        denial_code="CO-29",
        denial_type=DenialType.TIMELY_FILING,
        description="Claim submitted past the timely filing deadline",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _ai_appeal_json(claim, denial=None, citations=None, confidence=90):
    letter = f"Dear payer, please reconsider claim {claim.claim_number} for patient Doe. " + (
        "This service was medically necessary and properly documented. " * 6
    )
    if denial is not None:
        letter += f" Denial code {denial.denial_code} should be overturned."
    return json.dumps(
        {
            "title": "Appeal Letter",
            "appeal_letter": letter,
            "summary": "Appeal summary",
            "key_arguments": ["Medically necessary"],
            "citations": citations or [],
            "requested_action": "Please reprocess and pay this claim in full.",
            "attachments": ["Operative report"],
            "missing_information": [],
            "confidence": confidence,
        }
    )


# ---------------------------------------------------------------------------
# Citation Engine
# ---------------------------------------------------------------------------


def test_citations_for_denial_type_has_no_unsourced_jurisdiction_default():
    from app.appeals.citations import citations_for_denial_type
    from app.models.denial import DenialType

    assert citations_for_denial_type(DenialType.TIMELY_FILING) == []


def test_citations_for_denial_type_unmapped_category_returns_empty():
    from app.appeals.citations import citations_for_denial_type
    from app.models.denial import DenialType

    assert citations_for_denial_type(DenialType.OTHER) == []
    assert citations_for_denial_type(None) == []


def test_merge_citations_dedupes_by_source_and_reference():
    from app.appeals.citations import Citation, merge_citations

    verified_reference = Citation(
        source="Verified payer contract",
        reference="Section 4.2",
        description="Applicable reviewed filing requirement",
    )

    ai_citations = [
        {
            "source": verified_reference.source,
            "reference": verified_reference.reference,
            "relevance": "matches",
        }
    ]
    merged = merge_citations(ai_citations, [verified_reference])

    assert len(merged) == 1

    merged_new = merge_citations([], [verified_reference])
    assert len(merged_new) == 1
    assert merged_new[0]["source"] == "Verified payer contract"


def test_merge_citations_discards_unverified_model_citations():
    from app.appeals.citations import merge_citations

    merged = merge_citations(
        [
            {
                "source": "Invented payer manual",
                "reference": "Section 99",
                "relevance": "Model supplied",
            }
        ],
        [],
    )

    assert merged == []


@pytest.mark.asyncio
async def test_approved_policy_source_grounds_appeal_and_persists_provenance(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService
    from app.models.payer import PayerPolicySource

    content = "The payer accepts documented proof of timely original claim submission."
    source = PayerPolicySource(
        organization_id=org_id,
        payer_id=claim.payer_id,
        policy_code="TF-001",
        title="Reviewed Timely Filing Guidance",
        source_type="operating_guidance",
        jurisdiction="KE",
        version=1,
        status="approved",
        source_reference="Payer Circular 4, section 2",
        content=content,
        content_sha256="b" * 64,
        effective_from=claim.service_date - timedelta(days=1),
        denial_categories=["TIMELY_FILING"],
        procedure_codes=[],
        created_by=1,
        approved_by=2,
        change_reason="Initial reviewed version",
    )
    db.add(source)
    db.commit()

    prompts = []

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        prompts.append(prompt)
        return _ai_appeal_json(
            claim,
            denial,
            citations=[
                {
                    "source": source.title,
                    "reference": source.source_reference,
                    "relevance": "Supports reconsideration with filing evidence",
                }
            ],
        )

    monkeypatch.setattr(gateway, "generate", fake_generate)
    appeal = await AppealService(db, org_id).generate_appeal(claim.id)

    assert content in prompts[0]
    assert appeal.citations[0]["policy_source_id"] == source.id
    assert appeal.citations[0]["content_sha256"] == source.content_sha256
    assert appeal.grounding_report["grounded"] is True
    assert appeal.grounding_report["sources"][0]["id"] == source.id
    assert appeal.quality_score["grounding"] == 100


@pytest.mark.asyncio
async def test_unapproved_and_cross_tenant_sources_never_ground_appeal(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService
    from app.models.payer import PayerPolicySource

    pending = PayerPolicySource(
        organization_id=org_id,
        payer_id=claim.payer_id,
        policy_code="PENDING",
        title="Pending Guidance",
        source_type="operating_guidance",
        jurisdiction="KE",
        version=1,
        status="pending_approval",
        source_reference="Pending section 1",
        content="Pending content must not be available to the appeal generation prompt.",
        content_sha256="c" * 64,
        effective_from=claim.service_date,
        denial_categories=[],
        procedure_codes=[],
        created_by=1,
        change_reason="Pending review",
    )
    cross_tenant = PayerPolicySource(
        organization_id=999,
        payer_id=claim.payer_id,
        policy_code="OTHER-TENANT",
        title="Other Tenant Guidance",
        source_type="payer_contract",
        jurisdiction="KE",
        version=1,
        status="approved",
        source_reference="Other contract section 9",
        content="Cross-tenant content must never be available to this organization.",
        content_sha256="d" * 64,
        effective_from=claim.service_date,
        denial_categories=[],
        procedure_codes=[],
        created_by=1,
        change_reason="Other tenant source",
    )
    db.add_all([pending, cross_tenant])
    db.commit()
    prompts = []

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        prompts.append(prompt)
        return _ai_appeal_json(
            claim,
            denial,
            citations=[
                {
                    "source": "Invented Kenya payer manual",
                    "reference": "Section 99",
                    "relevance": "Not reviewed",
                }
            ],
        )

    monkeypatch.setattr(gateway, "generate", fake_generate)
    appeal = await AppealService(db, org_id).generate_appeal(claim.id)

    assert pending.content not in prompts[0]
    assert cross_tenant.content not in prompts[0]
    assert appeal.citations == []
    assert appeal.grounding_report["grounded"] is False
    assert appeal.grounding_report["rejected_model_citation_count"] == 1


@pytest.mark.asyncio
async def test_ungrounded_policy_assertion_is_rejected_before_persistence(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService
    from app.appeals.validator import AppealValidationError
    from app.models.appeal import Appeal

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        data = json.loads(_ai_appeal_json(claim, denial))
        data["appeal_letter"] += " The payer policy requires payment within thirty days."
        return json.dumps(data)

    monkeypatch.setattr(gateway, "generate", fake_generate)

    with pytest.raises(AppealValidationError, match="without an approved applicable source"):
        await AppealService(db, org_id).generate_appeal(claim.id)
    assert db.query(Appeal).count() == 0


# ---------------------------------------------------------------------------
# Appeal Quality Score
# ---------------------------------------------------------------------------


def test_score_appeal_high_quality_draft_scores_well():
    from app.appeals.evidence import EvidenceCheck
    from app.appeals.quality import score_appeal

    data = {
        "appeal_letter": "This appeal is well documented and professionally written. " * 15,
        "summary": "s",
        "requested_action": "Reprocess",
        "citations": [{"source": "CMS", "reference": "x", "relevance": "y"}],
        "confidence": 90,
    }
    evidence = EvidenceCheck(required=["Op report"], verified=["Op report"], needs_verification=[])

    score = score_appeal(data, evidence, kb_citation_available=True)

    assert score["completeness"] == 100
    assert score["evidence"] == 100
    assert score["tone"] == 100
    assert score["compliance"] == 100
    assert score["confidence"] == 90
    assert score["overall"] >= 90
    assert score["flagged_for_review"] is False


def test_score_appeal_low_quality_draft_flagged_for_review():
    from app.appeals.evidence import EvidenceCheck
    from app.appeals.quality import score_appeal

    data = {
        "appeal_letter": "Too short!!",
        "summary": "",
        "requested_action": "",
        "citations": [],
        "confidence": 10,
    }
    evidence = EvidenceCheck(required=["Op report"], verified=[], needs_verification=["Op report"])

    score = score_appeal(data, evidence, kb_citation_available=True)

    assert score["evidence"] == 0
    assert score["tone"] < 100
    assert score["compliance"] < 100
    assert score["overall"] < 70
    assert score["flagged_for_review"] is True


# ---------------------------------------------------------------------------
# Generation: citation merge, quality score, missing-evidence gate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_appeal_omits_unsourced_citations_and_scores_quality(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        return _ai_appeal_json(claim, denial, citations=[])

    monkeypatch.setattr(gateway, "generate", fake_generate)

    service = AppealService(db, org_id)
    appeal = await service.generate_appeal(claim.id)

    assert appeal.citations == []

    assert appeal.quality_score is not None
    for key in (
        "completeness",
        "evidence",
        "tone",
        "compliance",
        "confidence",
        "overall",
        "flagged_for_review",
    ):
        assert key in appeal.quality_score

    assert appeal.title == "Appeal Letter"
    assert appeal.attachments == ["Operative report"]


@pytest.mark.asyncio
async def test_generate_appeal_require_evidence_blocks_when_documents_missing(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.evidence import MissingEvidenceError
    from app.appeals.service import AppealService

    calls = []

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        calls.append(prompt)
        return _ai_appeal_json(claim, denial)

    monkeypatch.setattr(gateway, "generate", fake_generate)

    service = AppealService(db, org_id)
    with pytest.raises(MissingEvidenceError) as exc_info:
        await service.generate_appeal(claim.id, require_evidence=True)

    assert "Proof of timely submission" in exc_info.value.missing_documents
    # The AI should never have been called — generation was refused up front.
    assert calls == []


@pytest.mark.asyncio
async def test_generate_appeal_require_evidence_allows_when_documents_verified(
    db, org_id, claim, denial, monkeypatch
):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService
    from app.models.document import Document, DocumentType

    # An uploaded document whose filename overlaps the required-document
    # keywords ("timely", "submission") corroborates it as on file.
    db.add(
        Document(
            organization_id=org_id,
            claim_id=claim.id,
            document_type=DocumentType.OTHER,
            filename="proof_of_timely_submission.pdf",
            storage_path="/uploads/proof_of_timely_submission.pdf",
            content_type="application/pdf",
            file_size=1024,
            checksum="appeal-evidence-checksum",
        )
    )
    db.commit()

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        return _ai_appeal_json(claim, denial)

    monkeypatch.setattr(gateway, "generate", fake_generate)

    service = AppealService(db, org_id)
    appeal = await service.generate_appeal(claim.id, require_evidence=True)

    assert appeal.id is not None


# ---------------------------------------------------------------------------
# Submission Readiness
# ---------------------------------------------------------------------------


def _make_appeal(db, org_id, claim, **kwargs):
    from app.appeals.service import AppealService

    service = AppealService(db, org_id)
    appeal = service._persist_appeal(
        claim.id,
        None,
        {"appeal_letter": "Dear payer, please reconsider claim " + claim.claim_number},
        **kwargs,
    )
    return service, appeal


def test_check_submission_readiness_reports_blockers_without_raising(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)

    blockers = service.check_submission_readiness(appeal.id)

    assert any("approval" in b.lower() for b in blockers)


def test_submit_appeal_blocked_by_missing_documents(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim, missing_documents=["Operative report"])
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id)

    with pytest.raises(ValueError) as exc_info:
        service.submit_appeal(appeal.id)

    assert "Operative report" in str(exc_info.value)


def test_submit_appeal_blocked_by_timely_filing(db, org_id, claim):
    claim.service_date = date.today() - timedelta(days=400)
    db.commit()

    service, appeal = _make_appeal(db, org_id, claim)
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id)

    with pytest.raises(ValueError) as exc_info:
        service.submit_appeal(appeal.id)

    assert "timely filing" in str(exc_info.value).lower()


def test_submit_appeal_succeeds_when_all_checks_pass(db, org_id, claim):
    service, appeal = _make_appeal(db, org_id, claim)
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id)

    submitted = service.submit_appeal(appeal.id, confirmation_number="CONF-1")

    assert submitted.status.value == "submitted"


# ---------------------------------------------------------------------------
# AI Revision / regeneration versioning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_appeal_creates_new_version(db, org_id, claim, denial, monkeypatch):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService
    from app.models.appeal_version import AppealVersion

    async def fake_generate_v1(task, prompt, system=None, *, cache_key=None):
        return _ai_appeal_json(claim, denial)

    monkeypatch.setattr(gateway, "generate", fake_generate_v1)
    service = AppealService(db, org_id)
    appeal = await service.generate_appeal(claim.id)
    assert appeal.current_version == 1

    async def fake_generate_v2(task, prompt, system=None, *, cache_key=None):
        return _ai_appeal_json(claim, denial, confidence=95)

    monkeypatch.setattr(gateway, "generate", fake_generate_v2)
    revised = await service.regenerate_appeal(appeal.id)

    assert revised.current_version == 2
    # The AppealVersion table snapshots past states only — v1 (the original
    # AI draft) is preserved before being overwritten; the live v2 content
    # lives on the Appeal row itself until a further edit/regeneration.
    versions = (
        db.query(AppealVersion)
        .filter(AppealVersion.appeal_id == appeal.id)
        .order_by(AppealVersion.version_number)
        .all()
    )
    assert [v.version_number for v in versions] == [1]

    # Regenerating again snapshots v2 before moving to v3.
    revised_again = await service.regenerate_appeal(appeal.id)
    assert revised_again.current_version == 3
    versions = (
        db.query(AppealVersion)
        .filter(AppealVersion.appeal_id == appeal.id)
        .order_by(AppealVersion.version_number)
        .all()
    )
    assert [v.version_number for v in versions] == [1, 2]


@pytest.mark.asyncio
async def test_regenerate_appeal_rejects_once_approved(db, org_id, claim, denial, monkeypatch):
    from app.ai.gateway import gateway
    from app.appeals.service import AppealService

    async def fake_generate(task, prompt, system=None, *, cache_key=None):
        return _ai_appeal_json(claim, denial)

    monkeypatch.setattr(gateway, "generate", fake_generate)
    service = AppealService(db, org_id)
    appeal = await service.generate_appeal(claim.id)
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id)

    with pytest.raises(ValueError):
        await service.regenerate_appeal(appeal.id)


# ---------------------------------------------------------------------------
# Appeal Dashboard metrics
# ---------------------------------------------------------------------------


def test_appeal_dashboard_metrics(db, org_id, claim):
    from app.dashboard.analytics import AnalyticsRepository
    from app.models.appeal import Appeal, AppealStatus

    db.add_all(
        [
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.APPROVED,
                appeal_text="ready one",
                current_version=1,
            ),
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.REVIEW,
                appeal_text="waiting approval",
                current_version=1,
            ),
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.DRAFT,
                appeal_text="waiting docs",
                current_version=1,
                missing_documents=["Op report"],
            ),
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.SUBMITTED,
                appeal_text="submitted one",
                current_version=1,
            ),
        ]
    )
    db.commit()

    result = AnalyticsRepository(db, org_id).appeal_dashboard()

    assert result["appeals_generated_today"] == 4
    assert result["ready_for_submission"] == 1
    assert result["waiting_approval"] == 1
    assert result["waiting_documents"] == 1
    assert result["estimated_recoverable_revenue"] > 0


# ---------------------------------------------------------------------------
# Validator defaults for new structured fields
# ---------------------------------------------------------------------------


def test_validate_appeal_defaults_title_and_new_list_fields():
    from app.appeals.validator import validate_appeal

    data = {
        "appeal_letter": "Dear payer, please reconsider claim CLM-1. " + ("Padding text. " * 20)
    }
    validate_appeal(data, "CLM-1")

    assert data["title"] == "Appeal Letter — Claim CLM-1"
    assert data["attachments"] == []
    assert data["missing_information"] == []


# ---------------------------------------------------------------------------
# Extra context threading (documents/citations) in prompt builders
# ---------------------------------------------------------------------------


def test_appeal_generator_prompt_includes_extra_context(claim):
    from app.appeals.generator import AppealGenerator

    extra_context = {
        "documents_summary": "operative_report (op.pdf): appendectomy performed",
        "suggested_citations": ["CMS Medicare Claims Processing Manual — timely filing"],
    }
    prompt = AppealGenerator()._build_prompt(claim, None, None, None, extra_context)

    assert "appendectomy performed" in prompt
    assert "timely filing" in prompt


def test_sectioned_generator_context_includes_extra_context(claim):
    from app.appeals.sectioned_generator import SectionedAppealGenerator

    extra_context = {
        "documents_summary": "physician_notes (notes.pdf): follow up visit",
        "suggested_citations": ["CMS Social Security Act §1862"],
    }
    context = SectionedAppealGenerator()._build_context(claim, None, None, None, extra_context)

    assert "follow up visit" in context["documents_summary"]
    assert "1862" in context["suggested_citations"]
