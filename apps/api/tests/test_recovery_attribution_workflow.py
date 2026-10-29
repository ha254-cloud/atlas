from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.audit.actions import AuditAction
from app.billing.models import RecoveryFeeSchedule
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.invoice import InvoiceCreditNote, InvoiceReconciliationRun
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.models.recovery_attribution import (
    RecoveryAttributionDispute,
    RecoveryAttributionDisputeResolution,
    RecoveryAttributionVersion,
    RecoveryIntervention,
)
from app.models.user import User, UserRole
from app.payments.models import PaymentSource, PaymentStatus
from app.payments.schemas import PaymentIngest
from app.payments.service import PaymentService
from app.security.dependencies import get_current_user


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session = sessionmaker(bind=engine)()
    Base.metadata.create_all(engine)
    yield session
    session.close()


def _tenant(db, suffix: str):
    organization = Organization(
        name=f"Hospital {suffix}",
        slug=f"hospital-{suffix.lower()}",
        email=f"finance-{suffix.lower()}@atlas.test",
        currency="KES",
    )
    db.add(organization)
    db.flush()
    users = []
    for role_name in ("Verifier", "Approver", "Resolver"):
        user = User(
            organization_id=organization.id,
            email=f"{role_name.lower()}-{suffix.lower()}@atlas.test",
            password_hash="x",
            first_name=role_name,
            last_name=suffix,
            role=UserRole.OWNER,
        )
        db.add(user)
        users.append(user)
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name=suffix,
        medical_record_number=f"MRN-ATTR-{suffix}",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Social Health Authority",
        payer_code=f"SHA-ATTR-{suffix}",
    )
    db.add_all([patient, payer])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number=f"ATTR-{suffix}-001",
        status="denied",
        billed_amount=Decimal("700.00"),
        paid_amount=Decimal("0.00"),
        currency="KES",
        service_date=date(2026, 10, 1),
    )
    db.add(claim)
    db.flush()
    db.add(
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("10.00"),
            vat_percentage=Decimal("5.00"),
            currency="KES",
            payment_terms_days=30,
            dispute_period_days=30,
            effective_from=date(2026, 1, 1),
            created_by=users[0].id,
            reason="Signed Kenya design-partner terms",
        )
    )
    db.flush()
    payment = PaymentService(db, organization.id).ingest(
        PaymentIngest(
            claim_id=claim.id,
            payer_name="Social Health Authority",
            payment_reference=f"SHA-ATTR-{suffix}-PAYMENT",
            payment_date=date(2026, 10, 15),
            expected_amount=Decimal("700.00"),
            paid_amount=Decimal("700.00"),
            adjustment_amount=Decimal("0.00"),
            currency="KES",
            payment_method="eft",
            status=PaymentStatus.PAID,
            source=PaymentSource.CSV,
            raw_payload={"settlement": f"SHA-{suffix}"},
        ),
        actor_id=users[0].id,
        correlation_id=f"payment-attribution-{suffix}",
    ).payment
    recovery = db.query(Recovery).filter(
        Recovery.payment_id == payment.id,
        Recovery.claim_id == claim.id,
    ).one()
    return organization, users, claim, recovery


@pytest.fixture()
def seeded(db):
    organization, users, claim, recovery = _tenant(db, "ONE")
    foreign_organization, foreign_users, _foreign_claim, foreign_recovery = _tenant(
        db,
        "TWO",
    )
    db.commit()
    return {
        "organization": organization,
        "users": users,
        "claim": claim,
        "recovery": recovery,
        "foreign_organization": foreign_organization,
        "foreign_users": foreign_users,
        "foreign_recovery": foreign_recovery,
    }


@pytest.fixture()
def client(db, seeded):
    active_user = {"value": seeded["users"][0]}

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = (
        lambda: seeded["organization"].id
    )
    app.dependency_overrides[get_current_user] = lambda: active_user["value"]
    yield TestClient(app), active_user
    app.dependency_overrides.clear()


def test_attribution_dispute_credit_and_reconciliation_are_auditable(
    client,
    db,
    seeded,
    monkeypatch,
):
    test_client, active_user = client
    recovery = seeded["recovery"]
    claim = seeded["claim"]
    published = []
    monkeypatch.setattr(
        "app.recoveries.router.EventPublisher.publish",
        lambda _publisher, event_type, payload, organization_id=None: published.append(
            (event_type, payload, organization_id)
        ),
    )
    monkeypatch.setattr(
        "app.invoices.router.EventPublisher.publish",
        lambda _publisher, event_type, payload, organization_id=None: published.append(
            (event_type, payload, organization_id)
        ),
    )
    monkeypatch.setattr(
        "app.invoices.service.InvoicePDFService.render",
        lambda _invoice: b"%PDF-test",
    )
    monkeypatch.setattr(
        "app.invoices.service.save_bytes",
        lambda _content, _organization_id, _suffix: ("invoices/test.pdf", "sha256"),
    )

    verified = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/verify",
        json={"reason": "Finance verified the SHA cash settlement"},
    )
    assert verified.status_code == 200
    assert verified.json()["verified"] is True

    intervention = test_client.post(
        "/api/v1/recoveries/interventions",
        json={
            "claim_id": claim.id,
            "intervention_type": "underpayment_challenge",
            "occurred_at": "2026-10-10T08:00:00Z",
            "reason": "Atlas documented and submitted the underpayment challenge",
        },
    )
    assert intervention.status_code == 201
    intervention_id = intervention.json()["id"]

    self_approval = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/attributions",
        json={
            "status": "eligible",
            "intervention_id": intervention_id,
            "reason": "Attempt self-approval",
        },
    )
    assert self_approval.status_code == 400
    assert "must differ" in self_approval.json()["detail"]

    active_user["value"] = seeded["users"][1]
    attributed = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/attributions",
        json={
            "status": "eligible",
            "intervention_id": intervention_id,
            "reason": "Independent finance approval of Atlas attribution",
        },
    )
    assert attributed.status_code == 201
    assert attributed.json()["confirmed_amount"] == "700.00"
    assert attributed.json()["eligible_amount"] == "700.00"
    assert attributed.json()["currency"] == "KES"

    invoiced = test_client.post(
        "/api/v1/invoices/monthly",
        json={"year": 2026, "month": 10},
    )
    assert invoiced.status_code == 200
    invoice_id = invoiced.json()["id"]
    assert invoiced.json()["total_amount"] == 73.5
    assert invoiced.json()["lines"][0]["attribution_version_id"] == attributed.json()["id"]

    dispute = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/disputes",
        json={"reason": "Hospital disputes part of the attributed recovery"},
    )
    assert dispute.status_code == 201
    dispute_id = dispute.json()["id"]

    same_actor_resolution = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/disputes/{dispute_id}/resolve",
        json={
            "outcome": "partially_upheld",
            "eligible_amount": "500.00",
            "reason": "Attempt same-actor resolution",
        },
    )
    assert same_actor_resolution.status_code == 400
    assert "must differ" in same_actor_resolution.json()["detail"]

    active_user["value"] = seeded["users"][2]
    resolved = test_client.post(
        f"/api/v1/recoveries/{recovery.id}/disputes/{dispute_id}/resolve",
        json={
            "outcome": "partially_upheld",
            "eligible_amount": "500.00",
            "reason": "Independent review excludes KES 200 from success fees",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["attribution"]["version"] == 3
    assert resolved.json()["attribution"]["eligible_amount"] == "500.00"
    assert resolved.json()["credit_note_id"] is not None

    credit_note = db.query(InvoiceCreditNote).one()
    assert credit_note.payment_allocation_id is None
    assert credit_note.attribution_resolution_id == resolved.json()["resolution"]["id"]
    assert credit_note.recovered_adjustment_amount == Decimal("200.00")
    assert credit_note.total_credit_amount == Decimal("21.00")

    reconciled = test_client.post(
        f"/api/v1/invoices/{invoice_id}/reconciliations",
        json={"reason": "Independent month-end KES reconciliation"},
    )
    assert reconciled.status_code == 201
    assert reconciled.json()["status"] == "reconciled"
    assert reconciled.json()["source_payment_amount"] == "700.00"
    assert reconciled.json()["expected_net_amount"] == "52.50"
    assert reconciled.json()["actual_net_amount"] == "52.50"
    assert reconciled.json()["discrepancy_count"] == 0

    actions = {row.action for row in db.query(AuditLog).all()}
    assert {
        AuditAction.RECOVERY_VERIFIED,
        AuditAction.RECOVERY_INTERVENTION_RECORDED,
        AuditAction.RECOVERY_ATTRIBUTION_DECIDED,
        AuditAction.RECOVERY_ATTRIBUTION_DISPUTED,
        AuditAction.RECOVERY_ATTRIBUTION_DISPUTE_RESOLVED,
        AuditAction.INVOICE_CREDIT_NOTE_ISSUED,
        AuditAction.INVOICE_RECONCILED,
    }.issubset(actions)
    assert len(published) == 7


def test_attribution_records_are_immutable_and_tenant_scoped(client, db, seeded):
    test_client, _active_user = client
    foreign = test_client.get(
        f"/api/v1/recoveries/{seeded['foreign_recovery'].id}"
    )
    assert foreign.status_code == 404

    intervention = RecoveryIntervention(
        organization_id=seeded["organization"].id,
        claim_id=seeded["claim"].id,
        intervention_type="documented_follow_up",
        occurred_at=datetime(2026, 10, 10, tzinfo=UTC),
        actor_id=seeded["users"][0].id,
        reason="Immutable test intervention",
        correlation_id="immutable-intervention",
    )
    db.add(intervention)
    db.commit()
    intervention.reason = "Attempt overwrite"
    with pytest.raises(DatabaseError, match="revenue attribution ledgers are immutable"):
        db.commit()
    db.rollback()


def test_dispute_resolution_requires_exact_valid_money(db, seeded):
    recovery = seeded["recovery"]
    verifier, approver, resolver = seeded["users"]
    service = PaymentService(db, seeded["organization"].id)
    assert service.get(recovery.payment_id).organization_id == seeded["organization"].id

    from app.recoveries.schemas import (
        RecoveryAttributionCreate,
        RecoveryAttributionDisputeResolutionCreate,
        RecoveryInterventionCreate,
    )
    from app.recoveries.service import RecoveryAttributionService

    attribution_service = RecoveryAttributionService(
        db,
        seeded["organization"].id,
    )
    attribution_service.verify(
        recovery.id,
        verified_by=verifier.id,
        reason="Verify settlement",
    )
    intervention = attribution_service.record_intervention(
        RecoveryInterventionCreate(
            claim_id=seeded["claim"].id,
            intervention_type="underpayment_challenge",
            occurred_at=datetime(2026, 10, 10, tzinfo=UTC),
            reason="Documented challenge",
        ),
        actor_id=verifier.id,
        correlation_id="money-intervention",
    )
    attribution_service.decide_attribution(
        recovery.id,
        RecoveryAttributionCreate(
            status="eligible",
            intervention_id=intervention.id,
            reason="Approve attribution",
        ),
        actor_id=approver.id,
        correlation_id="money-attribution",
    )
    dispute = attribution_service.open_dispute(
        recovery.id,
        actor_id=approver.id,
        reason="Challenge amount",
        correlation_id="money-dispute",
    )
    with pytest.raises(ValueError, match="below the prior eligible amount"):
        attribution_service.resolve_dispute(
            recovery.id,
            dispute.id,
            RecoveryAttributionDisputeResolutionCreate(
                outcome="partially_upheld",
                eligible_amount=Decimal("700.00"),
                reason="Invalid unchanged amount",
            ),
            actor_id=resolver.id,
            correlation_id="money-resolution",
        )

    assert db.query(RecoveryAttributionVersion).count() == 2
    assert db.query(RecoveryAttributionDispute).count() == 1
    assert db.query(RecoveryAttributionDisputeResolution).count() == 0
    assert db.query(InvoiceReconciliationRun).count() == 0
