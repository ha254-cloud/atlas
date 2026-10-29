import asyncio
from datetime import UTC, date, datetime, time
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
    from app.billing.models import RecoveryFeeSchedule
    from app.models.appeal import Appeal, AppealStatus
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.user import User, UserRole

    organization = Organization(name="Atlas Hospital", email="billing@atlas.test")
    db.add(organization)
    db.flush()
    db.add(RecoveryFeeSchedule(
        organization_id=organization.id,
        fee_percentage=Decimal("5.00"),
        vat_percentage=Decimal("5.00"),
        currency="KES",
        payment_terms_days=30,
        effective_from=date(2020, 1, 1),
        reason="Test recovery contract",
    ))
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
    db.add_all([patient, payer, user])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-SUB-001",
        status="denied",
        billed_amount=Decimal("10000.00"),
        paid_amount=Decimal("0.00"),
        currency="KES",
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
    from app.models.user import User, UserRole
    from app.recoveries.schemas import (
        RecoveryAttributionCreate,
        RecoveryInterventionCreate,
    )
    from app.services.invoice_service import InvoiceService
    from app.services.recovery_service import RecoveryAttributionService
    from app.submissions.service import SubmissionService

    organization, user, claim, appeal = approved_appeal
    service = SubmissionService(db, organization.id)
    submission = asyncio.run(service.submit(
        appeal.id,
        connector="mock",
        submitted_by=user.id,
        connector_options={"initial_status": "paid", "paid_amount": "8000.00"},
    ))

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

    attribution_service = RecoveryAttributionService(db, organization.id)
    attribution_service.verify(
        recovery.id,
        verified_by=user.id,
        reason="Payment reconciled to remittance",
    )
    approver = User(
        organization_id=organization.id,
        email="approver@atlas.test",
        password_hash="x",
        first_name="Independent",
        last_name="Approver",
        role=UserRole.ADMIN,
    )
    db.add(approver)
    db.flush()
    intervention = attribution_service.record_intervention(
        RecoveryInterventionCreate(
            claim_id=claim.id,
            submission_id=submission.id,
            intervention_type="appeal_submission",
            occurred_at=datetime.combine(
                recovery.payment_date,
                time.min,
                tzinfo=UTC,
            ),
            reason="Approved appeal preceded the payer settlement",
        ),
        actor_id=user.id,
        correlation_id="submission-intervention",
    )
    attribution_service.decide_attribution(
        recovery.id,
        RecoveryAttributionCreate(
            status="eligible",
            intervention_id=intervention.id,
            reason="Independent finance attribution approval",
        ),
        actor_id=approver.id,
        correlation_id="submission-attribution",
    )
    db.commit()
    invoice_service = InvoiceService(db, organization.id)
    invoice = invoice_service.generate_monthly(
        recovery.payment_date.year,
        recovery.payment_date.month,
    )
    assert invoice.total_recovered_amount == Decimal("8000.00")
    assert invoice.total_fee_amount == Decimal("400.00")
    assert invoice.vat_amount == Decimal("20.00")
    assert invoice.total_amount == Decimal("420.00")
    assert invoice.currency == "KES"
    assert invoice.pdf_path is not None
    assert len(invoice.lines) == 1
    assert invoice.lines[0].claim_id == claim.id
    assert invoice_service.generate_monthly(
        recovery.payment_date.year,
        recovery.payment_date.month,
    ).id == invoice.id

    sent = invoice_service.mark_sent(invoice.id)
    assert sent.status == InvoiceStatus.SENT
    paid_invoice = invoice_service.mark_paid(invoice.id)
    assert paid_invoice.status == InvoiceStatus.PAID


def test_submission_still_requires_human_approval(db, approved_appeal):
    from app.models.appeal import AppealStatus
    from app.models.submission import Submission
    from app.submissions.service import SubmissionService

    organization, _, _, appeal = approved_appeal
    appeal.status = AppealStatus.DRAFT
    db.commit()

    with pytest.raises(ValueError, match="human-approved"):
        asyncio.run(SubmissionService(db, organization.id).submit(appeal.id, "mock"))

    assert db.query(Submission).count() == 0


def test_submission_uses_claim_payer_connector_when_not_overridden(db, approved_appeal):
    from app.models.submission import SubmissionStatus
    from app.submissions.service import SubmissionService

    organization, user, claim, appeal = approved_appeal
    claim.payer.connector_name = "sandbox"
    claim.payer.submission_method = "manual"
    db.commit()

    submission = asyncio.run(
        SubmissionService(db, organization.id).submit(
            appeal.id,
            submitted_by=user.id,
        )
    )

    assert submission.connector == "sandbox"
    assert submission.status == SubmissionStatus.SUBMITTED


def test_submission_events_and_timeline_follow_status_changes(
    monkeypatch, db, approved_appeal
):
    from app.events.event_types import EventType
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.models.submission import SubmissionStatus
    from app.submissions.service import SubmissionService

    published = []
    monkeypatch.setattr(
        "app.submissions.service.EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {"publish": lambda self, event_type, payload: published.append(event_type)},
        )(),
    )
    organization, user, _, appeal = approved_appeal
    service = SubmissionService(db, organization.id)
    submission = asyncio.run(service.submit(
        appeal.id,
        connector="mock",
        submitted_by=user.id,
        connector_options={"initial_status": "acknowledged"},
    ))
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
    organization, _, claim, appeal = approved_appeal
    from app.models.user import User, UserRole

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

    refreshed = client.post(
        f"/api/v1/submissions/{submission['id']}/refresh"
    )
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
        json={"reason": "Payment reconciled to remittance"},
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    payment_date = recovery["payment_date"].split("-")
    intervention = client.post(
        "/api/v1/recoveries/interventions",
        json={
            "claim_id": claim.id,
            "submission_id": submission["id"],
            "intervention_type": "appeal_submission",
            "occurred_at": f"{recovery['payment_date']}T00:00:00Z",
            "reason": "Approved appeal preceded the payer settlement",
        },
    )
    assert intervention.status_code == 201
    approver = User(
        organization_id=organization.id,
        email="api-approver@atlas.test",
        password_hash="x",
        first_name="API",
        last_name="Approver",
        role=UserRole.ADMIN,
    )
    db.add(approver)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: approver
    attributed = client.post(
        f"/api/v1/recoveries/{recovery['id']}/attributions",
        json={
            "status": "eligible",
            "intervention_id": intervention.json()["id"],
            "reason": "Independent finance attribution approval",
        },
    )
    assert attributed.status_code == 201

    invoice = client.post(
        "/api/v1/invoices/monthly",
        json={"year": int(payment_date[0]), "month": int(payment_date[1])},
    )
    assert invoice.status_code == 200
    assert invoice.json()["total_recovered_amount"] == 7500.0
    assert invoice.json()["total_fee_amount"] == 375.0
    assert invoice.json()["vat_amount"] == 18.75
    assert invoice.json()["total_amount"] == 393.75
    assert invoice.json()["lines"][0]["claim_id"] == appeal.claim_id


def test_submission_recovery_and_invoice_get_list_are_tenant_scoped(
    db, approved_appeal
):
    from app.invoices.repository import InvoiceRepository
    from app.invoices.service import InvoiceService
    from app.models.invoice import Invoice, InvoiceStatus
    from app.models.organization import Organization
    from app.models.recovery import Recovery
    from app.models.submission import Submission, SubmissionStatus
    from app.payments.models import Payment, PaymentSource, PaymentStatus
    from app.recoveries.repository import RecoveryRepository
    from app.recoveries.service import RecoveryAttributionService
    from app.submissions.repository import SubmissionRepository
    from app.submissions.service import SubmissionService

    organization, _, claim, appeal = approved_appeal
    other_organization = Organization(name="Other Hospital", email="other@atlas.test")
    db.add(other_organization)
    db.flush()

    own_submission = Submission(
        organization_id=organization.id,
        claim_id=claim.id,
        appeal_id=appeal.id,
        connector="mock",
        status=SubmissionStatus.SUBMITTED,
    )
    other_submission = Submission(
        organization_id=other_organization.id,
        claim_id=claim.id,
        appeal_id=appeal.id + 1000,
        connector="mock",
        status=SubmissionStatus.SUBMITTED,
    )
    db.add_all([own_submission, other_submission])
    db.flush()

    own_payment = Payment(
        organization_id=organization.id,
        claim_id=claim.id,
        submission_id=own_submission.id,
        payer_name="Mock Health",
        payment_reference="TENANT-OWN-PAYMENT",
        payment_date=date(2026, 7, 15),
        expected_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        adjustment_amount=Decimal("0.00"),
        currency="USD",
        status=PaymentStatus.PAID,
        source=PaymentSource.MANUAL,
        raw_payload={"fixture": True},
        correlation_id="tenant-own-payment",
    )
    other_payment = Payment(
        organization_id=other_organization.id,
        claim_id=claim.id,
        submission_id=other_submission.id,
        payer_name="Mock Health",
        payment_reference="TENANT-OTHER-PAYMENT",
        payment_date=date(2026, 7, 16),
        expected_amount=Decimal("200.00"),
        paid_amount=Decimal("200.00"),
        adjustment_amount=Decimal("0.00"),
        currency="USD",
        status=PaymentStatus.PAID,
        source=PaymentSource.MANUAL,
        raw_payload={"fixture": True},
        correlation_id="tenant-other-payment",
    )
    db.add_all([own_payment, other_payment])
    db.flush()

    own_recovery = Recovery(
        organization_id=organization.id,
        claim_id=claim.id,
        submission_id=own_submission.id,
        payment_id=own_payment.id,
        paid_amount=Decimal("100.00"),
        expected_amount=Decimal("100.00"),
        recovered_amount=Decimal("100.00"),
        recovery_percentage=Decimal("100.00"),
        atlas_fee_percentage=Decimal("5.00"),
        atlas_fee_amount=Decimal("5.00"),
        payment_date=date(2026, 7, 15),
        verified=False,
    )
    other_recovery = Recovery(
        organization_id=other_organization.id,
        claim_id=claim.id,
        submission_id=other_submission.id,
        payment_id=other_payment.id,
        paid_amount=Decimal("200.00"),
        expected_amount=Decimal("200.00"),
        recovered_amount=Decimal("200.00"),
        recovery_percentage=Decimal("100.00"),
        atlas_fee_percentage=Decimal("5.00"),
        atlas_fee_amount=Decimal("10.00"),
        payment_date=date(2026, 7, 16),
        verified=False,
    )
    own_invoice = Invoice(
        organization_id=organization.id,
        invoice_number="ATL-TENANT-OWN",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        status=InvoiceStatus.DRAFT,
        total_recovered_amount=Decimal("100.00"),
        total_fee_amount=Decimal("5.00"),
        vat_percentage=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("5.00"),
        currency="USD",
        payment_terms_days=30,
        due_date=date(2026, 8, 30),
        billing_name=organization.name,
        billing_email=organization.email,
    )
    other_invoice = Invoice(
        organization_id=other_organization.id,
        invoice_number="ATL-TENANT-OTHER",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        status=InvoiceStatus.DRAFT,
        total_recovered_amount=Decimal("200.00"),
        total_fee_amount=Decimal("10.00"),
        vat_percentage=Decimal("0.00"),
        vat_amount=Decimal("0.00"),
        total_amount=Decimal("10.00"),
        currency="USD",
        payment_terms_days=30,
        due_date=date(2026, 8, 30),
        billing_name=other_organization.name,
        billing_email=other_organization.email,
    )
    db.add_all([own_recovery, other_recovery, own_invoice, other_invoice])
    db.commit()

    submission_repository = SubmissionRepository(db, organization.id)
    assert submission_repository.get(other_submission.id) is None
    assert [row.id for row in submission_repository.list()] == [own_submission.id]
    submission_service = SubmissionService(db, organization.id)
    with pytest.raises(ValueError, match="not found"):
        submission_service.get(other_submission.id)
    assert [row.id for row in submission_service.list()] == [own_submission.id]

    recovery_repository = RecoveryRepository(db, organization.id)
    assert recovery_repository.get(other_recovery.id) is None
    assert [row.id for row in recovery_repository.list()] == [own_recovery.id]
    recovery_service = RecoveryAttributionService(db, organization.id)
    with pytest.raises(ValueError, match="not found"):
        recovery_service.get(other_recovery.id)
    assert [row.id for row in recovery_service.list()] == [own_recovery.id]

    invoice_repository = InvoiceRepository(db, organization.id)
    assert invoice_repository.get(other_invoice.id) is None
    assert [row.id for row in invoice_repository.list()] == [own_invoice.id]
    invoice_service = InvoiceService(db, organization.id)
    with pytest.raises(ValueError, match="not found"):
        invoice_service.get(other_invoice.id)
    assert [row.id for row in invoice_service.list()] == [own_invoice.id]
