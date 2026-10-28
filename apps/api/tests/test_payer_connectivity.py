import asyncio
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 - register all tables before create_all
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
def appeal_bundle(db):
    from app.billing.models import RecoveryFeeSchedule
    from app.models.appeal import Appeal, AppealStatus
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.recovery_case import RecoveryCase, RecoveryStatus

    organization = Organization(
        name="Atlas Hospital",
        slug="atlas-hospital",
        email="billing@atlas.test",
        status="active",
    )
    db.add(organization)
    db.flush()
    db.add(RecoveryFeeSchedule(
        organization_id=organization.id,
        fee_percentage=Decimal("5.00"),
        vat_percentage=Decimal("0.00"),
        currency="USD",
        payment_terms_days=30,
        effective_from=date(2020, 1, 1),
        reason="Test recovery contract",
    ))
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-PAYER-1",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Blue Cross",
        payer_code="BCBS",
    )
    db.add_all([patient, payer])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-PAYER-001",
        status="denied",
        billed_amount=Decimal("25000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date.today() - timedelta(days=20),
    )
    db.add(claim)
    db.flush()
    recovery_case = RecoveryCase(
        organization_id=organization.id,
        claim_id=claim.id,
        recovery_score=Decimal("88.00"),
        estimated_value=Decimal("20000.00"),
        status=RecoveryStatus.APPEALED,
        recommendation="Appeal",
    )
    db.add(recovery_case)
    db.flush()
    appeal = Appeal(
        organization_id=organization.id,
        claim_id=claim.id,
        recovery_case_id=recovery_case.id,
        status=AppealStatus.APPROVED,
        appeal_text="Please reconsider this medically necessary claim.",
        attachments=[],
        missing_documents=[],
    )
    db.add(appeal)
    db.commit()
    return organization, claim, recovery_case, appeal


def test_status_mapping_normalizes_payer_vocabulary():
    from app.models.appeal_submission import AppealSubmissionStatus
    from app.payer_connectivity.status import normalize_status

    assert normalize_status("availity", "Accepted") == AppealSubmissionStatus.ACKNOWLEDGED
    assert normalize_status("waystar", "In Medical Review") == AppealSubmissionStatus.UNDER_REVIEW
    assert normalize_status("sandbox", "Paid") == AppealSubmissionStatus.PAID
    with pytest.raises(ValueError, match="mapping must be configured"):
        normalize_status("availity", "Mystery Queue")


def test_electronic_submission_requires_human_approval(db, appeal_bundle):
    from app.models.appeal import AppealStatus
    from app.models.appeal_submission import AppealSubmission
    from app.payer_connectivity.service import PayerSubmissionService

    organization, _, _, appeal = appeal_bundle
    appeal.status = AppealStatus.DRAFT
    db.commit()

    with pytest.raises(ValueError, match="human-approved"):
        asyncio.run(PayerSubmissionService(db, organization.id).submit(appeal.id, "sandbox"))

    assert db.query(AppealSubmission).count() == 0


def test_submission_is_idempotent_and_updates_appeal(db, appeal_bundle):
    from app.models.appeal import AppealStatus
    from app.models.appeal_submission import AppealSubmissionEvent, AppealSubmissionStatus
    from app.payer_connectivity.service import PayerSubmissionService

    organization, _, _, appeal = appeal_bundle
    service = PayerSubmissionService(db, organization.id)
    first = asyncio.run(service.submit(appeal.id, "sandbox"))
    second = asyncio.run(service.submit(appeal.id, "sandbox"))

    assert first.id == second.id
    assert first.status == AppealSubmissionStatus.SUBMITTED
    assert first.external_tracking_id.startswith("ATLAS-")
    assert appeal.status == AppealStatus.SUBMITTED
    assert appeal.confirmation_number == first.external_tracking_id
    statuses = [row.status for row in db.query(AppealSubmissionEvent).order_by(AppealSubmissionEvent.id).all()]
    assert statuses == [AppealSubmissionStatus.SUBMITTING, AppealSubmissionStatus.SUBMITTED]


def test_paid_status_updates_claim_recovery_and_timeline(db, appeal_bundle):
    from app.models.appeal_submission import AppealSubmissionStatus
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.models.recovery_case import RecoveryStatus
    from app.payer_connectivity.service import PayerSubmissionService

    organization, claim, recovery_case, appeal = appeal_bundle
    service = PayerSubmissionService(db, organization.id)
    submission = asyncio.run(service.submit(
        appeal.id,
        "sandbox",
        connector_options={"initial_status": "Paid", "paid_amount": "18000.00"},
    ))
    refreshed = asyncio.run(service.refresh(submission.id))

    assert refreshed.status == AppealSubmissionStatus.PAID
    assert claim.paid_amount == Decimal("18000.00")
    assert recovery_case.status == RecoveryStatus.RECOVERED
    assert recovery_case.recovered_amount == Decimal("18000.00")
    assert recovery_case.payment_received_at is not None
    event_types = [row.event_type for row in db.query(ClaimEvent).all()]
    assert ClaimEventType.APPEAL_STATUS_UPDATED in event_types
    assert ClaimEventType.PAYMENT_RECEIVED in event_types


def test_paid_without_amount_requires_reconciliation(db, appeal_bundle):
    from app.models.appeal_submission import AppealSubmissionStatus
    from app.payer_connectivity.service import PayerSubmissionService

    organization, claim, recovery_case, appeal = appeal_bundle
    service = PayerSubmissionService(db, organization.id)
    submission = asyncio.run(service.submit(
        appeal.id,
        "sandbox",
        connector_options={"initial_status": "Paid"},
    ))
    refreshed = asyncio.run(service.refresh(submission.id))

    assert refreshed.status == AppealSubmissionStatus.PAID
    assert "requires reconciliation" in refreshed.last_error
    assert claim.paid_amount == Decimal("0.00")
    assert recovery_case.recovered_amount is None


def test_executive_summary_uses_submission_records(db, appeal_bundle):
    from app.payer_connectivity.analytics import PayerConnectivityAnalytics
    from app.payer_connectivity.service import PayerSubmissionService

    organization, _, _, appeal = appeal_bundle
    service = PayerSubmissionService(db, organization.id)
    asyncio.run(service.submit(appeal.id, "sandbox"))

    summary = PayerConnectivityAnalytics(db, organization.id).executive_summary()

    assert summary["submitted_today"] == 1
    assert summary["pending"] == 1
    assert summary["paid"] == 0
    assert summary["average_response_days"] is None


def test_failed_submission_can_retry_same_record(db, appeal_bundle):
    from app.models.appeal_submission import AppealSubmission, AppealSubmissionStatus
    from app.payer_connectivity.service import PayerSubmissionService

    organization, _, _, appeal = appeal_bundle
    service = PayerSubmissionService(db, organization.id)
    failed = AppealSubmission(
        organization_id=organization.id,
        appeal_id=appeal.id,
        connector="sandbox",
        status=AppealSubmissionStatus.FAILED,
        retry_count=1,
        last_error="temporary outage",
    )
    db.add(failed)
    db.commit()

    retried = asyncio.run(service.submit(appeal.id, "sandbox"))

    assert retried.id == failed.id
    assert retried.status == AppealSubmissionStatus.SUBMITTED
    assert retried.last_error is None
    assert db.query(AppealSubmission).count() == 1