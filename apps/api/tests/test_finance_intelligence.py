from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.finance.service import FinanceIntelligenceService
from app.main import app
from app.models.claim import Claim
from app.models.denial import Denial, DenialType
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole
from app.payments.models import Payment, PaymentSource, PaymentStatus
from app.security.dependencies import get_current_user


@pytest.fixture
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


def _organization(db, suffix: str) -> tuple[Organization, Patient, Payer]:
    organization = Organization(
        name=f"Hospital {suffix}",
        email=f"finance-{suffix.lower()}@atlas.test",
        currency="KES",
        country="KE",
    )
    db.add(organization)
    db.flush()
    patient = Patient(
        organization_id=organization.id,
        first_name="Amina",
        last_name="Wanjiku",
        medical_record_number=f"MRN-{suffix}",
        date_of_birth=date(1985, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Jubilee",
        payer_code=f"JUB-{suffix}",
    )
    db.add_all([patient, payer])
    db.flush()
    return organization, patient, payer


def _payment(
    organization_id: int,
    claim_id: int,
    reference: str,
    amount: str,
) -> Payment:
    return Payment(
        organization_id=organization_id,
        claim_id=claim_id,
        payer_name="Jubilee",
        payment_reference=reference,
        payment_date=date.today(),
        expected_amount=Decimal("200000.00"),
        paid_amount=Decimal(amount),
        adjustment_amount=Decimal("0.00"),
        currency="KES",
        status=PaymentStatus.PARTIAL,
        source=PaymentSource.MANUAL,
        raw_payload={"reference": reference},
        correlation_id=f"correlation-{reference}",
    )


def test_finance_overview_uses_partial_payment_ledger_and_tenant_scope(db):
    organization, patient, payer = _organization(db, "ONE")
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-KENYA-001",
        status="denied",
        billed_amount=Decimal("200000.00"),
        paid_amount=Decimal("120000.00"),
        service_date=date.today() - timedelta(days=20),
    )
    db.add(claim)
    db.flush()
    first = _payment(organization.id, claim.id, "EFT-001", "70000.00")
    second = _payment(organization.id, claim.id, "EFT-002", "50000.00")
    db.add_all([first, second])
    db.flush()
    db.add_all(
        [
            Recovery(
                organization_id=organization.id,
                claim_id=claim.id,
                payment_id=first.id,
                paid_amount=first.paid_amount,
                expected_amount=first.expected_amount,
                recovered_amount=first.paid_amount,
                recovery_percentage=Decimal("35.00"),
                atlas_fee_percentage=Decimal("15.00"),
                atlas_fee_amount=Decimal("10500.00"),
                payment_date=first.payment_date,
                verified=True,
            ),
            Recovery(
                organization_id=organization.id,
                claim_id=claim.id,
                payment_id=second.id,
                paid_amount=second.paid_amount,
                expected_amount=second.expected_amount,
                recovered_amount=second.paid_amount,
                recovery_percentage=Decimal("25.00"),
                atlas_fee_percentage=Decimal("15.00"),
                atlas_fee_amount=Decimal("7500.00"),
                payment_date=second.payment_date,
                verified=True,
            ),
            RecoveryCase(
                organization_id=organization.id,
                claim_id=claim.id,
                recovery_score=Decimal("75.00"),
                estimated_value=Decimal("30000.00"),
                status=RecoveryStatus.OPEN,
                recommendation="Appeal missing authorization balance",
            ),
            Denial(
                organization_id=organization.id,
                claim_id=claim.id,
                denial_code="AUTH",
                denial_type=DenialType.PRIOR_AUTH,
                description="Missing authorization",
            ),
        ]
    )

    other_organization, other_patient, other_payer = _organization(db, "TWO")
    db.add(
        Claim(
            organization_id=other_organization.id,
            patient_id=other_patient.id,
            payer_id=other_payer.id,
            claim_number="CLM-OTHER-001",
            status="denied",
            billed_amount=Decimal("900000.00"),
            paid_amount=Decimal("0.00"),
            service_date=date.today(),
        )
    )
    db.commit()

    overview = FinanceIntelligenceService(db, organization.id).overview()

    assert overview.executive.currency == "KES"
    assert overview.executive.todays_collections == 120000.0
    assert overview.executive.potential_revenue == 200000.0
    assert overview.executive.collected_revenue == 120000.0
    assert overview.executive.outstanding_claims == 80000.0
    assert overview.executive.recoverable_revenue == 30000.0
    assert overview.executive.atlas_attributed_recoveries == 120000.0
    assert overview.executive.unclassified_leakage == 50000.0
    assert overview.executive.collection_rate_pct == 60.0
    assert overview.executive.average_payment_days == 20.0
    assert overview.payers[0].outstanding_amount == 80000.0
    assert overview.payers[0].recovered_amount == 120000.0
    assert overview.denial_leakage[0].denial_type == "prior_authorization"
    assert overview.denial_leakage[0].outstanding_amount == 80000.0
    assert overview.forecast.expected_collections == 22500.0
    assert overview.forecast.confidence_pct == 75.0
    assert overview.reconciliation.matched_payment_count == 2
    assert overview.reconciliation.matched_payment_amount == 120000.0


def test_unmatched_payments_are_visible_to_reconciliation(db):
    organization, _, _ = _organization(db, "ONE")
    payment = _payment(organization.id, 1, "UNMATCHED-001", "5000.00")
    payment.claim_id = None
    db.add(payment)
    db.commit()

    reconciliation = FinanceIntelligenceService(db, organization.id).overview().reconciliation

    assert reconciliation.unmatched_payment_count == 1
    assert reconciliation.unmatched_payment_amount == 5000.0
    assert reconciliation.matched_payment_count == 0


def test_finance_api_requires_authentication():
    response = TestClient(app).get("/api/v1/finance/overview")

    assert response.status_code == 401


def test_finance_api_returns_authenticated_tenant_snapshot(db):
    organization, _, _ = _organization(db, "ONE")
    user = User(
        organization_id=organization.id,
        email="ceo@atlas.test",
        password_hash="x",
        first_name="Chief",
        last_name="Executive",
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = TestClient(app).get("/api/v1/finance/executive")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["currency"] == "KES"
    assert response.json()["potential_revenue"] == 0.0
