"""
API-level test for the recovery-workspace outcome endpoint — confirms
recording a payment outcome now also appends a PAYMENT_RECEIVED entry to the
claim's audit timeline (previously the ClaimEventType existed but nothing
ever recorded it).
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.security.dependencies import get_current_user


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def seed(db_session):
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.recovery_case import RecoveryCase, RecoveryStatus
    from app.models.user import User, UserRole

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    db_session.add(org)
    db_session.flush()

    patient = Patient(
        organization_id=org.id,
        first_name="John",
        last_name="Smith",
        medical_record_number="MRN-001",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Aetna", payer_code="AETNA")
    user = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add_all([patient, payer, user])
    db_session.flush()

    claim = Claim(
        organization_id=org.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-0001",
        status="denied",
        billed_amount=Decimal("1500.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 1, 5),
    )
    db_session.add(claim)
    db_session.flush()

    recovery_case = RecoveryCase(
        organization_id=org.id,
        claim_id=claim.id,
        recovery_score=Decimal("75.00"),
        estimated_value=Decimal("1200.00"),
        status=RecoveryStatus.OPEN,
        recommendation="Review claim and pursue recovery",
    )
    db_session.add(recovery_case)
    db_session.commit()

    return {"org": org, "claim": claim, "recovery_case": recovery_case, "user": user}


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_record_outcome_cannot_manufacture_payment_evidence(client, seed):
    response = client.post(
        "/api/v1/recovery-workspace/record-outcome",
        json={
            "recovery_case_id": seed["recovery_case"].id,
            "recovered_amount": 1200.00,
            "atlas_fee_pct": 5.0,
        },
    )
    assert response.status_code == 410
    assert "Ingest or reconcile payment evidence" in response.json()["detail"]
    assert seed["recovery_case"].payment_received_at is None
    assert seed["recovery_case"].recovered_amount is None
    assert seed["recovery_case"].invoice_generated is False

    claim_id = seed["claim"].id
    timeline_response = client.get(f"/api/v1/claims/{claim_id}/timeline")
    assert timeline_response.status_code == 200
    events = timeline_response.json()
    assert not any(e["event_type"] == "claim.payment_received" for e in events)

    payments_response = client.get("/api/v1/payments")
    assert payments_response.status_code == 200
    payments = payments_response.json()
    assert payments["summary"] == {
        "total_recovered": 0.0,
        "total_fees": 0.0,
        "net_recovered": 0.0,
        "payment_count": 0,
        "invoices_generated": 0,
    }
    assert payments["payments"] == []

    tracking_response = client.get(f"/api/v1/payments/claims/{claim_id}/tracking")
    assert tracking_response.status_code == 200
    tracking = tracking_response.json()
    assert tracking["payment_received"] is False
    assert tracking["recovery_verified"] is False
    assert tracking["invoice_created"] is False
    assert {stage["key"]: stage["state"] for stage in tracking["stages"]} == {
        "appeal_submitted": "pending",
        "payer_response": "pending",
        "payment_received": "pending",
        "recovery_verified": "pending",
        "invoice_created": "pending",
    }
