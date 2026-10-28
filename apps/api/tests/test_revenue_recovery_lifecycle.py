from datetime import date
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
from app.models.claim import Claim
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole
from app.payments.models import Payment, PaymentSource, PaymentStatus
from app.recovery.models import RecoveryAccount, RecoveryLifecycleEvent, RecoveryLifecycleState
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
    user = User(
        organization_id=organization.id,
        email=f"owner-{suffix.lower()}@atlas.test",
        password_hash="x",
        first_name="Finance",
        last_name=suffix,
        role=UserRole.OWNER,
    )
    patient = Patient(
        organization_id=organization.id,
        first_name="Test",
        last_name=suffix,
        medical_record_number=f"MRN-{suffix}",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name=f"Payer {suffix}",
        payer_code=f"PAY-{suffix}",
    )
    db.add_all([user, patient, payer])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number=f"LIFECYCLE-{suffix}",
        status="denied",
        billed_amount=Decimal("200000.00"),
        paid_amount=Decimal("150000.00"),
        service_date=date(2026, 1, 1),
    )
    db.add(claim)
    db.flush()
    db.add(
        RecoveryCase(
            organization_id=organization.id,
            claim_id=claim.id,
            recovery_score=Decimal("92.00"),
            estimated_value=Decimal("50000.00"),
            status=RecoveryStatus.IN_PROGRESS,
            recommendation="Pursue the supported outstanding balance",
        )
    )
    db.flush()
    return organization, user, claim


def _verified_recovery(db, organization, claim, *, amount: Decimal, sequence: int):
    payment = Payment(
        organization_id=organization.id,
        claim_id=claim.id,
        payer_name="Payer",
        payment_reference=f"EFT-{organization.id}-{sequence}",
        payment_date=date(2026, 7, sequence),
        expected_amount=claim.billed_amount,
        paid_amount=amount,
        adjustment_amount=Decimal("0.00"),
        currency="KES",
        payment_method="eft",
        status=PaymentStatus.PARTIAL,
        source=PaymentSource.CSV,
        raw_payload={"sequence": sequence},
        correlation_id=f"00000000-0000-0000-{organization.id:04d}-{sequence:012d}",
    )
    db.add(payment)
    db.flush()
    recovery = Recovery(
        organization_id=organization.id,
        claim_id=claim.id,
        payment_id=payment.id,
        paid_amount=amount,
        expected_amount=claim.billed_amount,
        recovered_amount=amount,
        recovery_percentage=(amount / claim.billed_amount * Decimal(100)),
        atlas_fee_percentage=Decimal("15.00"),
        atlas_fee_amount=amount * Decimal("0.15"),
        payment_date=payment.payment_date,
        verified=True,
        verified_by=None,
        verification_reason="Imported verified settlement evidence",
    )
    db.add(recovery)
    db.flush()
    return recovery


@pytest.fixture()
def seeded(db):
    organization, user, claim = _tenant(db, "ONE")
    _verified_recovery(db, organization, claim, amount=Decimal("120000.00"), sequence=1)
    _verified_recovery(db, organization, claim, amount=Decimal("30000.00"), sequence=2)
    other_organization, _other_user, other_claim = _tenant(db, "TWO")
    foreign_account = RecoveryAccount(
        organization_id=other_organization.id,
        claim_id=other_claim.id,
        currency="KES",
        state=RecoveryLifecycleState.DRAFT,
        version=1,
    )
    db.add(foreign_account)
    db.commit()
    return organization, user, claim, foreign_account


@pytest.fixture()
def client(db, seeded):
    organization, user, _claim, _foreign_account = seeded

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_recovery_lifecycle_reconciles_every_shilling_before_close(client, db, seeded):
    _organization, _user, claim, _foreign_account = seeded
    opened = client.post(
        f"/api/v1/recovery/lifecycle/claims/{claim.id}",
        json={"reason": "Track the full financial recovery lifecycle"},
    )
    assert opened.status_code == 201
    detail = opened.json()
    account_id = detail["account"]["id"]
    assert detail["account"]["state"] == "partially_paid"
    assert detail["account"]["version"] == 3
    assert detail["position"] == {
        "claim_id": claim.id,
        "account_id": account_id,
        "currency": "KES",
        "original_amount": "200000.00",
        "recovered_amount": "150000.00",
        "outstanding_amount": "50000.00",
        "recoverable_amount": "50000.00",
        "expected_recovery_amount": "50000.00",
        "contract_adjustment_amount": "0.00",
        "written_off_amount": "0.00",
        "recovery_probability_pct": "92.00",
        "fully_accounted": False,
        "as_of": detail["position"]["as_of"],
    }

    portfolio = client.get("/api/v1/recovery/lifecycle/portfolio")
    assert portfolio.status_code == 200
    assert portfolio.json()["recoverable_revenue_index_pct"] == "100.00"
    assert portfolio.json()["atlas_recoveries"] == "150000.00"
    assert portfolio.json()["atlas_fees"] == "22500.00"

    moved = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/transitions",
        json={
            "to_state": "outstanding_balance",
            "expected_version": 3,
            "reason": "Continue recovery work on the remaining balance",
            "idempotency_key": "transition-outstanding-001",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["account"]["version"] == 4

    overallocated = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/allocations",
        json={
            "allocation_type": "contract_adjustment",
            "amount": "60000.00",
            "reason_code": "contract_tariff",
            "reason": "Attempt an invalid excess adjustment",
            "expected_version": 4,
            "idempotency_key": "allocation-invalid-001",
        },
    )
    assert overallocated.status_code == 400
    assert overallocated.json()["detail"] == "Allocation exceeds the outstanding balance"

    written_off = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/allocations",
        json={
            "allocation_type": "write_off",
            "amount": "10000.00",
            "reason_code": "approved_economic_write_off",
            "reason": "Finance approved a limited economic write-off",
            "expected_version": 4,
            "idempotency_key": "allocation-writeoff-001",
        },
    )
    assert written_off.status_code == 200
    assert written_off.json()["account"]["state"] == "written_off"
    assert written_off.json()["account"]["version"] == 5

    premature_close = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/transitions",
        json={
            "to_state": "closed",
            "expected_version": 5,
            "reason": "Attempt closure before complete allocation",
            "idempotency_key": "transition-close-early-001",
        },
    )
    assert premature_close.status_code == 400
    assert "balance remains unaccounted" in premature_close.json()["detail"]

    adjusted_payload = {
        "allocation_type": "contract_adjustment",
        "amount": "40000.00",
        "reason_code": "signed_contract_adjustment",
        "reason": "Allocate the signed payer contract adjustment",
        "expected_version": 5,
        "idempotency_key": "allocation-adjustment-001",
    }
    adjusted = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/allocations",
        json=adjusted_payload,
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["position"]["outstanding_amount"] == "0.00"
    assert adjusted.json()["account"]["version"] == 6

    replay = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/allocations",
        json=adjusted_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["account"]["version"] == 6

    closed = client.post(
        f"/api/v1/recovery/lifecycle/accounts/{account_id}/transitions",
        json={
            "to_state": "closed",
            "expected_version": 6,
            "reason": "Every shilling is now allocated",
            "idempotency_key": "transition-close-final-001",
        },
    )
    assert closed.status_code == 200
    assert closed.json()["account"]["state"] == "closed"
    assert closed.json()["position"]["fully_accounted"] is True
    assert (
        db.query(RecoveryLifecycleEvent)
        .filter(RecoveryLifecycleEvent.account_id == account_id)
        .count()
        == 7
    )


def test_recovery_lifecycle_account_is_cross_tenant_safe(client, seeded):
    _organization, _user, _claim, foreign_account = seeded

    response = client.get(f"/api/v1/recovery/lifecycle/accounts/{foreign_account.id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Recovery account not found"


def test_lifecycle_reconciliation_worker_is_tenant_scoped_and_idempotent(db, seeded, monkeypatch):
    organization, _user, claim, foreign_account = seeded
    organization_id = organization.id
    claim_id = claim.id
    foreign_organization_id = foreign_account.organization_id
    monkeypatch.setattr("app.db.database.get_db", lambda: iter([db]))

    from app.workers.tasks import reconcile_recovery_lifecycles

    first = reconcile_recovery_lifecycles.run()
    account = (
        db.query(RecoveryAccount)
        .filter_by(
            organization_id=organization_id,
            claim_id=claim_id,
        )
        .one()
    )
    account_id = account.id
    first_event_count = db.query(RecoveryLifecycleEvent).filter_by(account_id=account_id).count()

    second = reconcile_recovery_lifecycles.run()

    assert first == {"processed": 2, "organizations": 2}
    assert second == first
    assert db.query(RecoveryAccount).filter_by(organization_id=organization_id).count() == 1
    assert db.query(RecoveryAccount).filter_by(organization_id=foreign_organization_id).count() == 1
    assert first_event_count == 3
    assert db.query(RecoveryLifecycleEvent).filter_by(account_id=account_id).count() == 3
    assert {
        event.actor_type
        for event in db.query(RecoveryLifecycleEvent).filter_by(account_id=account_id).all()
    } == {"system"}
