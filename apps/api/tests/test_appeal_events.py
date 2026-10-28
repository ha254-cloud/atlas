"""
Tests that appeal generation/submission actually populate the claim's audit
timeline — ClaimEventType.APPEAL_GENERATED/APPEAL_SUBMITTED existed as enum
values but were never recorded anywhere before this change.
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
    from app.models.patient import Patient
    from app.models.payer import Payer

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
        claim_number="CLM-APPEAL-001",
        status="denied",
        billed_amount=Decimal("500.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 1, 10),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def test_persist_appeal_records_appeal_generated_event(db, org_id, claim):
    from app.appeals.service import AppealService
    from app.models.claim_event import ClaimEvent, ClaimEventType

    service = AppealService(db, org_id)
    appeal = service._persist_appeal(
        claim.id,
        None,
        {"appeal_letter": "Dear payer, please reconsider claim " + claim.claim_number},
    )

    assert appeal.id is not None
    event = (
        db.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == claim.id,
            ClaimEvent.event_type == ClaimEventType.APPEAL_GENERATED,
        )
        .first()
    )
    assert event is not None
    assert str(appeal.id) in str(event.event_metadata)


def test_submit_appeal_records_appeal_submitted_event(db, org_id, claim):
    from app.appeals.service import AppealService
    from app.models.claim_event import ClaimEvent, ClaimEventType

    service = AppealService(db, org_id)
    appeal = service._persist_appeal(
        claim.id,
        None,
        {"appeal_letter": "Dear payer, please reconsider claim " + claim.claim_number},
    )

    # Appeals must go through human review + approval before submission —
    # AI-generated drafts are never auto-submitted.
    service.submit_for_review(appeal.id)
    service.approve_appeal(appeal.id)
    submitted = service.submit_appeal(appeal.id, confirmation_number="CONF-123")

    assert submitted.status.value == "submitted"
    assert submitted.confirmation_number == "CONF-123"
    event = (
        db.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == claim.id,
            ClaimEvent.event_type == ClaimEventType.APPEAL_SUBMITTED,
        )
        .first()
    )
    assert event is not None


def test_submit_appeal_without_approval_raises(db, org_id, claim):
    from app.appeals.service import AppealService

    service = AppealService(db, org_id)
    appeal = service._persist_appeal(
        claim.id,
        None,
        {"appeal_letter": "Dear payer, please reconsider claim " + claim.claim_number},
    )

    with pytest.raises(ValueError):
        service.submit_appeal(appeal.id)
