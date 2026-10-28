from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.database import Base, get_db
from app.main import app
from app.models.ai_call_log import AICallLog
from app.models.audit_log import AuditLog
from app.models.integration import Integration, IntegrationStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User, UserRole
from app.organizations.models import Organization
from app.security.dependencies import get_current_user


@pytest.fixture()
def db_session():
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
def seed(db_session):
    atlas = Organization(
        name="Atlas Operations",
        email="platform@atlas.example",
        currency="KES",
        subscription_plan="enterprise",
        status="active",
        settings={},
    )
    hospital = Organization(
        name="Nairobi Test Hospital",
        email="hospital@example.test",
        currency="KES",
        subscription_plan="trial",
        status="active",
        settings={},
    )
    suspended = Organization(
        name="Suspended Test Hospital",
        email="suspended@example.test",
        currency="USD",
        subscription_plan="enterprise",
        status="suspended",
        is_active=False,
        settings={},
    )
    db_session.add_all([atlas, hospital, suspended])
    db_session.flush()
    superuser = User(
        organization_id=atlas.id,
        email="superuser@atlas.example",
        password_hash="x",
        first_name="Atlas",
        last_name="Operator",
        role=UserRole.ADMIN,
        is_superuser=True,
    )
    hospital_admin = User(
        organization_id=hospital.id,
        email="admin@hospital.example",
        password_hash="x",
        first_name="Hospital",
        last_name="Admin",
        role=UserRole.ADMIN,
        is_superuser=False,
    )
    db_session.add_all([superuser, hospital_admin])
    db_session.flush()
    db_session.add_all(
        [
            Invoice(
                organization_id=hospital.id,
                invoice_number="ATLAS-KES-PAID",
                period_start=date.today().replace(day=1),
                period_end=date.today(),
                status=InvoiceStatus.PAID,
                total_recovered_amount=Decimal("100000.00"),
                total_fee_amount=Decimal("15000.00"),
                vat_percentage=Decimal("16.00"),
                vat_amount=Decimal("2400.00"),
                total_amount=Decimal("17400.00"),
                currency="KES",
                payment_terms_days=30,
                due_date=date.today(),
                billing_name=hospital.name,
                billing_email=hospital.email,
            ),
            Invoice(
                organization_id=suspended.id,
                invoice_number="ATLAS-USD-PAID",
                period_start=date.today().replace(day=1),
                period_end=date.today(),
                status=InvoiceStatus.PAID,
                total_recovered_amount=Decimal("1000.00"),
                total_fee_amount=Decimal("100.00"),
                vat_percentage=Decimal("0.00"),
                vat_amount=Decimal("0.00"),
                total_amount=Decimal("100.00"),
                currency="USD",
                payment_terms_days=30,
                due_date=date.today(),
                billing_name=suspended.name,
                billing_email=suspended.email,
            ),
            Invoice(
                organization_id=hospital.id,
                invoice_number="ATLAS-KES-OVERDUE",
                period_start=date.today().replace(day=1) - timedelta(days=31),
                period_end=date.today().replace(day=1) - timedelta(days=1),
                status=InvoiceStatus.SENT,
                total_recovered_amount=Decimal("50000.00"),
                total_fee_amount=Decimal("7500.00"),
                vat_percentage=Decimal("16.00"),
                vat_amount=Decimal("1200.00"),
                total_amount=Decimal("8700.00"),
                currency="KES",
                payment_terms_days=30,
                due_date=date.today() - timedelta(days=1),
                billing_name=hospital.name,
                billing_email=hospital.email,
            ),
            AICallLog(
                organization_id=hospital.id,
                task="claim_analysis",
                provider="openai",
                model="gpt-test",
                prompt_version="1.0",
                input_tokens=120,
                output_tokens=30,
                cost_usd=Decimal("0.012500"),
                duration_ms=800,
                cache_hit=False,
            ),
            Integration(
                organization_id=hospital.id,
                provider="sftp",
                status=IntegrationStatus.ERROR,
                last_error="Synthetic connection failure",
                claims_imported_count=0,
                settings={},
            ),
        ]
    )
    db_session.commit()
    return {
        "atlas": atlas,
        "hospital": hospital,
        "suspended": suspended,
        "superuser": superuser,
        "hospital_admin": hospital_admin,
    }


@pytest.fixture()
def client(db_session, seed):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: seed["superuser"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_hospital_admin_cannot_access_platform_summary(client, seed):
    app.dependency_overrides[get_current_user] = lambda: seed["hospital_admin"]

    response = client.get("/api/v1/platform-admin/summary")

    assert response.status_code == 403
    assert response.json()["detail"] == "Atlas platform administrator access is required"


def test_superuser_summary_uses_real_currency_safe_aggregates_and_audits(client, db_session, seed):
    response = client.get("/api/v1/platform-admin/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["customers"] == {"total": 3, "active": 2, "trial": 1, "suspended": 1}
    assert body["atlas_revenue"]["paid_invoices"] == [
        {"currency": "KES", "amount": "17400.00"},
        {"currency": "USD", "amount": "100.00"},
    ]
    assert body["atlas_revenue"]["overdue_invoices"] == [{"currency": "KES", "amount": "8700.00"}]
    assert body["ai_operations"]["requests_today"] == 1
    assert body["ai_operations"]["tokens_today"] == 150
    assert body["integration_errors"] == 1
    assert body["system_health"]["redis"] == "not_instrumented"
    assert "MRR and ARR" in body["unavailable_metrics"]
    assert any("invoice ATLAS-KES-OVERDUE is overdue" in item["message"] for item in body["alerts"])

    audit = db_session.query(AuditLog).filter(AuditLog.action == "platform_admin.viewed").one()
    assert audit.organization_id == seed["atlas"].id
    assert audit.user_id == seed["superuser"].id
    assert audit.metadata_json == {"scope": "summary", "access_mode": "aggregate_only"}


def test_hospital_list_excludes_confidential_fields_and_audits(client, db_session):
    response = client.get("/api/v1/platform-admin/hospitals")

    assert response.status_code == 200
    hospital = next(item for item in response.json() if item["name"] == "Nairobi Test Hospital")
    assert hospital["subscription_plan"] == "trial"
    assert hospital["currency"] == "KES"
    assert hospital["atlas_revenue"] == [{"currency": "KES", "amount": "17400.00"}]
    assert "email" not in hospital
    assert "settings" not in hospital
    assert "claims" not in hospital

    audit = db_session.query(AuditLog).filter(AuditLog.action == "platform_admin.viewed").one()
    assert audit.metadata_json["scope"] == "hospitals"
