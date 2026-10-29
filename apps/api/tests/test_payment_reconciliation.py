from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.billing.models import RecoveryFeeSchedule
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.events.event_types import EventType
from app.main import app
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
from app.payments.models import Payment, PaymentSource, PaymentStatus
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
    owner = User(
        organization_id=organization.id,
        email=f"owner-{suffix.lower()}@atlas.test",
        password_hash="x",
        first_name="Finance",
        last_name=suffix,
        role=UserRole.OWNER,
    )
    viewer = User(
        organization_id=organization.id,
        email=f"viewer-{suffix.lower()}@atlas.test",
        password_hash="x",
        first_name="View",
        last_name=suffix,
        role=UserRole.VIEWER,
    )
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name=suffix,
        medical_record_number=f"MRN-{suffix}",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Social Health Authority",
        payer_code=f"SHA-{suffix}",
    )
    db.add_all([owner, viewer, patient, payer])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number=f"CLM-{suffix}",
        status="denied",
        billed_amount=Decimal("10000.00"),
        paid_amount=Decimal("0.00"),
        currency="KES",
        service_date=date(2026, 10, 1),
    )
    db.add(claim)
    db.flush()
    return organization, owner, viewer, claim


@pytest.fixture()
def seeded(db):
    organization, owner, viewer, claim = _tenant(db, "ONE")
    other_organization, _other_owner, _other_viewer, foreign_claim = _tenant(db, "TWO")
    db.add(
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("10.00"),
            vat_percentage=Decimal("0.00"),
            currency="KES",
            payment_terms_days=30,
            effective_from=date(2026, 1, 1),
            reason="Design-partner fee schedule",
        )
    )
    payment = Payment(
        organization_id=organization.id,
        payer_name="Social Health Authority",
        payment_reference="SHA-EFT-001",
        payment_date=date(2026, 10, 15),
        expected_amount=Decimal("10000.00"),
        paid_amount=Decimal("7500.00"),
        adjustment_amount=Decimal("2500.00"),
        currency="KES",
        payment_method="eft",
        status=PaymentStatus.PAID,
        source=PaymentSource.CSV,
        raw_payload={
            "claim_reference": claim.claim_number,
            "foreign_reference": foreign_claim.claim_number,
        },
        correlation_id="payment-reconciliation-001",
    )
    foreign_payment = Payment(
        organization_id=other_organization.id,
        payer_name="Social Health Authority",
        payment_reference="SHA-EFT-FOREIGN",
        payment_date=date(2026, 10, 15),
        expected_amount=Decimal("10000.00"),
        paid_amount=Decimal("5000.00"),
        adjustment_amount=Decimal("5000.00"),
        currency="KES",
        status=PaymentStatus.PAID,
        source=PaymentSource.CSV,
        raw_payload={"claim_reference": foreign_claim.claim_number},
        correlation_id="payment-reconciliation-foreign",
    )
    db.add_all([payment, foreign_payment])
    db.commit()
    return {
        "organization": organization,
        "owner": owner,
        "viewer": viewer,
        "claim": claim,
        "foreign_claim": foreign_claim,
        "payment": payment,
        "foreign_payment": foreign_payment,
    }


@pytest.fixture()
def client(db, seeded):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seeded["organization"].id
    app.dependency_overrides[get_current_user] = lambda: seeded["owner"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_candidates_and_match_are_tenant_scoped_and_audited(
    client,
    db,
    seeded,
    monkeypatch,
):
    payment = seeded["payment"]
    claim = seeded["claim"]
    published = []
    monkeypatch.setattr(
        "app.api.v1.payments.EventPublisher.publish",
        lambda _publisher, event_type, payload, organization_id=None: published.append(
            (event_type, payload, organization_id)
        ),
    )

    candidates = client.get(f"/api/v1/payments/records/{payment.id}/candidates")
    assert candidates.status_code == 200
    assert [row["claim_id"] for row in candidates.json()] == [claim.id]
    assert candidates.json()[0]["confidence"] == 90

    matched = client.post(
        f"/api/v1/payments/records/{payment.id}/match",
        json={
            "claim_id": claim.id,
            "reason": "Matched to the claim reference in SHA payment advice",
        },
    )
    assert matched.status_code == 200
    assert matched.json()["claim_id"] == claim.id
    assert matched.json()["matched_by_id"] == seeded["owner"].id
    assert matched.json()["matching_method"] == "manual"
    assert matched.json()["matching_reason"] == (
        "Matched to the claim reference in SHA payment advice"
    )

    audit = db.query(AuditLog).filter(AuditLog.action == "payment.matched").one()
    assert audit.organization_id == seeded["organization"].id
    assert audit.user_id == seeded["owner"].id
    assert audit.reason == "Matched to the claim reference in SHA payment advice"
    assert audit.correlation_id == matched.headers["x-request-id"]
    assert audit.correlation_id != payment.correlation_id
    assert audit.before_state == {"claim_id": None, "submission_id": None}
    assert audit.after_state["claim_id"] == claim.id
    assert published == [
        (
            EventType.PAYMENT_MATCHED,
            {
                "organization_id": seeded["organization"].id,
                "payment_id": payment.id,
                "claim_id": claim.id,
                "recovery_id": payment.recovery.id,
                "actor_id": seeded["owner"].id,
                "correlation_id": matched.headers["x-request-id"],
            },
            seeded["organization"].id,
        )
    ]


def test_cross_tenant_payment_is_not_disclosed(client, seeded):
    foreign_payment = seeded["foreign_payment"]

    candidates = client.get(
        f"/api/v1/payments/records/{foreign_payment.id}/candidates"
    )
    match = client.post(
        f"/api/v1/payments/records/{foreign_payment.id}/match",
        json={
            "claim_id": seeded["claim"].id,
            "reason": "Attempt cross-tenant reconciliation",
        },
    )

    assert candidates.status_code == 404
    assert match.status_code == 404


def test_viewer_cannot_reconcile_payments(client, seeded):
    app.dependency_overrides[get_current_user] = lambda: seeded["viewer"]

    candidates = client.get(
        f"/api/v1/payments/records/{seeded['payment'].id}/candidates"
    )
    match = client.post(
        f"/api/v1/payments/records/{seeded['payment'].id}/match",
        json={
            "claim_id": seeded["claim"].id,
            "reason": "Viewer must not reconcile payment evidence",
        },
    )

    assert candidates.status_code == 403
    assert match.status_code == 403
