import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.security.dependencies import get_current_user


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def approved_appeal(db):
    from app.billing.service import RecoveryFeeScheduleService
    from app.models.appeal import Appeal, AppealStatus
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.user import User, UserRole

    organization = Organization(name="Atlas Hospital", email="billing@atlas.test")
    db.add(organization)
    db.flush()
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-SUB-1",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Mock Health",
        payer_code="MOCK",
    )
    user = User(
        organization_id=organization.id,
        email="reviewer@atlas.test",
        password_hash="x",
        first_name="Human",
        last_name="Reviewer",
        role=UserRole.ADMIN,
    )
    approver = User(
        organization_id=organization.id,
        email="approver@atlas.test",
        password_hash="x",
        first_name="Finance",
        last_name="Approver",
        role=UserRole.ADMIN,
    )
    db.add_all([patient, payer, user, approver])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-SUB-001",
        status="denied",
        billed_amount=Decimal("10000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 7, 1),
    )
    db.add(claim)
    db.flush()
    appeal = Appeal(
        organization_id=organization.id,
        claim_id=claim.id,
        status=AppealStatus.APPROVED,
        appeal_text="Please reconsider this claim.",
        attachments=[],
        missing_documents=[],
        approved_by=user.id,
    )
    db.add(appeal)
    RecoveryFeeScheduleService(db, organization.id).create(
        fee_percentage=Decimal("5.00"),
        vat_percentage=Decimal("0.00"),
        currency="KES",
        payment_terms_days=30,
        effective_from=date(2020, 1, 1),
        effective_to=None,
        created_by=user.id,
        reason="Submission engine test fee schedule",
    )
    db.commit()
    return organization, user, claim, appeal


@pytest.fixture()
def client(db, approved_appeal):
    organization, user, _, _ = approved_appeal

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_mock_submission_to_recovery_and_monthly_invoice(db, approved_appeal):
    from app.models.invoice import InvoiceStatus
    from app.models.recovery import Recovery
    from app.models.submission import SubmissionEvent, SubmissionStatus
    from app.models.user import User
    from app.recoveries.schemas import (
        RecoveryAttributionCreate,
        RecoveryInterventionCreate,
    )
    from app.recoveries.service import RecoveryAttributionService
    from app.services.invoice_service import InvoiceService
    from app.services.submission_service import SubmissionService

    organization, user, claim, appeal = approved_appeal
    service = SubmissionService(db, organization.id)
    submission = asyncio.run(
        service.submit(
            appeal.id,
            connector="mock",
            submitted_by=user.id,
            connector_options={"initial_status": "paid", "paid_amount": "8000.00"},
        )
    )

    assert submission.status == SubmissionStatus.SUBMITTED
    assert submission.claim_id == claim.id
    assert submission.external_reference.startswith("ATLAS-")
    assert [event.status for event in db.query(SubmissionEvent).all()] == [
        SubmissionStatus.SUBMITTING,
        SubmissionStatus.SUBMITTED,
    ]

    paid = asyncio.run(service.status(submission.id))
    assert paid.status == SubmissionStatus.PAID
    assert paid.completed_at is not None
    recovery = db.query(Recovery).filter(Recovery.submission_id == submission.id).one()
    assert recovery.paid_amount == Decimal("8000.00")
    assert recovery.expected_amount == Decimal("10000.00")
    assert recovery.recovered_amount == Decimal("8000.00")
    assert recovery.atlas_fee_percentage == Decimal("5.00")
    assert recovery.atlas_fee_amount == Decimal("400.00")
    assert recovery.verified is False

    approver = db.query(User).filter(User.email == "approver@atlas.test").one()
    recovery_service = RecoveryAttributionService(db, organization.id)
    recovery_service.verify(
        recovery.id,
        verified_by=user.id,
        reason="Confirmed against settlement evidence",
    )
    intervention = recovery_service.record_intervention(
        RecoveryInterventionCreate(
            claim_id=claim.id,
            submission_id=submission.id,
            intervention_type="appeal_submission",
            occurred_at=datetime.now(UTC),
            reason="Approved appeal was submitted before payment",
        ),
        actor_id=user.id,
        correlation_id="submission-engine-intervention",
    )
    recovery_service.decide_attribution(
        recovery.id,
        RecoveryAttributionCreate(
            status="eligible",
            intervention_id=intervention.id,
            reason="Independent finance approval of Atlas attribution",
        ),
        actor_id=approver.id,
        correlation_id="submission-engine-attribution",
    )
    db.commit()
    invoice_service = InvoiceService(db, organization.id)
    invoice = invoice_service.generate_monthly(
        recovery.payment_date.year,
        recovery.payment_date.month,
    )
    assert invoice.total_recovered_amount == Decimal("8000.00")
    assert invoice.total_fee_amount == Decimal("400.00")
    assert len(invoice.lines) == 1
    assert invoice.lines[0].claim_id == claim.id
    assert (
        invoice_service.generate_monthly(
            recovery.payment_date.year,
            recovery.payment_date.month,
        ).id
        == invoice.id
    )

    sent = invoice_service.mark_sent(invoice.id)
    assert sent.status == InvoiceStatus.SENT
    paid_invoice = invoice_service.mark_paid(invoice.id)
    assert paid_invoice.status == InvoiceStatus.PAID


def test_submission_still_requires_human_approval(db, approved_appeal):
    from app.models.appeal import AppealStatus
    from app.models.submission import Submission
    from app.services.submission_service import SubmissionService

    organization, _, _, appeal = approved_appeal
    appeal.status = AppealStatus.DRAFT
    db.commit()

    with pytest.raises(ValueError, match="human-approved"):
        asyncio.run(SubmissionService(db, organization.id).submit(appeal.id, "mock"))

    assert db.query(Submission).count() == 0


def test_submission_events_and_timeline_follow_status_changes(monkeypatch, db, approved_appeal):
    from app.events.event_types import EventType
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.models.submission import SubmissionStatus
    from app.services.submission_service import SubmissionService

    published = []
    monkeypatch.setattr(
        "app.services.submission_service.EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {"publish": lambda self, event_type, payload: published.append(event_type)},
        )(),
    )
    organization, user, _, appeal = approved_appeal
    service = SubmissionService(db, organization.id)
    submission = asyncio.run(
        service.submit(
            appeal.id,
            connector="mock",
            submitted_by=user.id,
            connector_options={"initial_status": "acknowledged"},
        )
    )
    acknowledged = asyncio.run(service.status(submission.id))

    assert acknowledged.status == SubmissionStatus.ACKNOWLEDGED
    assert acknowledged.acknowledged_at is not None
    assert published == [
        EventType.SUBMISSION_CREATED,
        EventType.SUBMISSION_SUBMITTED,
        EventType.APPEAL_SUBMISSION_UPDATED,
        EventType.SUBMISSION_ACKNOWLEDGED,
        EventType.APPEAL_SUBMISSION_UPDATED,
    ]
    timeline = [row.event_type for row in db.query(ClaimEvent).all()]
    assert ClaimEventType.APPEAL_SUBMITTED in timeline
    assert ClaimEventType.APPEAL_STATUS_UPDATED in timeline


def test_submission_recovery_and_invoice_api(client, db, approved_appeal):
    from app.models.user import User

    organization, _, claim, appeal = approved_appeal
    response = client.post(
        f"/api/v1/appeals/{appeal.id}/submissions",
        json={
            "connector": "mock",
            "connector_options": {
                "initial_status": "paid",
                "paid_amount": "7500.00",
            },
        },
    )
    assert response.status_code == 200
    submission = response.json()
    assert submission["status"] == "submitted"
    assert submission["external_reference"].startswith("ATLAS-")

    refreshed = client.post(f"/api/v1/submissions/{submission['id']}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "paid"

    recoveries = client.get("/api/v1/recoveries")
    assert recoveries.status_code == 200
    recovery = recoveries.json()[0]
    assert recovery["submission_id"] == submission["id"]
    assert recovery["atlas_fee_amount"] == 375.0
    assert recovery["verified"] is False

    verified = client.post(
        f"/api/v1/recoveries/{recovery['id']}/verify",
        json={"reason": "Confirmed against settlement evidence"},
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    intervention = client.post(
        "/api/v1/recoveries/interventions",
        json={
            "claim_id": claim.id,
            "submission_id": submission["id"],
            "intervention_type": "appeal_submission",
            "occurred_at": datetime.now(UTC).isoformat(),
            "reason": "Approved appeal was submitted before payment",
        },
    )
    assert intervention.status_code == 201

    approver = db.query(User).filter(User.email == "approver@atlas.test").one()
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: approver
    attribution = client.post(
        f"/api/v1/recoveries/{recovery['id']}/attributions",
        json={
            "status": "eligible",
            "intervention_id": intervention.json()["id"],
            "reason": "Independent finance approval of Atlas attribution",
        },
    )
    assert attribution.status_code == 201

    payment_date = recovery["payment_date"].split("-")
    invoice = client.post(
        "/api/v1/invoices/monthly",
        json={"year": int(payment_date[0]), "month": int(payment_date[1])},
    )
    assert invoice.status_code == 200
    assert invoice.json()["total_recovered_amount"] == 7500.0
    assert invoice.json()["total_fee_amount"] == 375.0
    assert invoice.json()["lines"][0]["claim_id"] == appeal.claim_id
