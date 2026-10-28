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
    session = sessionmaker(bind=engine)()
    Base.metadata.create_all(engine)
    yield session
    session.close()


@pytest.fixture()
def tenant(db):
    from app.models.organization import Organization
    from app.models.user import User, UserRole

    organization = Organization(name="Nairobi Hospital", email="billing@nairobi.test")
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email="admin@nairobi.test",
        password_hash="x",
        first_name="Nairobi",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    return organization, user


@pytest.fixture()
def client(db, tenant):
    organization, user = tenant

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_check_reports_not_configured_without_integration(client, db, tenant):
    organization, _user = tenant
    from app.models.payer import Payer

    payer = Payer(organization_id=organization.id, name="AAR", payer_code="AAR")
    db.add(payer)
    db.commit()

    response = client.get(f"/api/v1/payers/{payer.id}/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["failure_count"] == 0

    db.refresh(payer)
    assert payer.last_health_status == "not_configured"
    assert payer.last_health_checked_at is not None


def test_health_check_uses_bound_integration_connector(client, db, tenant, monkeypatch):
    organization, _user = tenant
    from app.models.integration import Integration
    from app.models.payer import Payer

    integration = Integration(
        organization_id=organization.id,
        provider="waystar",
        settings={"submission_connector": "mock"},
    )
    db.add(integration)
    db.flush()
    payer = Payer(
        organization_id=organization.id,
        name="Britam Health",
        payer_code="BRITAM",
        submission_method="api",
        status_method="api",
        payment_method="api",
        supports_api=True,
        connector_name="mock",
        integration_id=integration.id,
    )
    db.add(payer)
    db.commit()

    async def _fake_health_check(self, integration_id, organization_id, correlation_id=None):
        return {"connected": True, "latency_ms": 12.5}

    from app.integrations.manager import IntegrationManager

    monkeypatch.setattr(IntegrationManager, "health_check", _fake_health_check)

    response = client.get(f"/api/v1/payers/{payer.id}/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["latency_ms"] == 12.5


def test_health_check_records_failure_and_increments_count(client, db, tenant, monkeypatch):
    organization, _user = tenant
    from app.models.integration import Integration
    from app.models.payer import Payer

    integration = Integration(
        organization_id=organization.id,
        provider="waystar",
        settings={"submission_connector": "mock"},
    )
    db.add(integration)
    db.flush()
    payer = Payer(
        organization_id=organization.id,
        name="Britam Health",
        payer_code="BRITAM2",
        submission_method="api",
        status_method="api",
        payment_method="api",
        supports_api=True,
        connector_name="mock",
        integration_id=integration.id,
    )
    db.add(payer)
    db.commit()

    from app.integrations.exceptions import IntegrationError
    from app.integrations.manager import IntegrationManager

    async def _failing_health_check(self, integration_id, organization_id, correlation_id=None):
        raise IntegrationError("Health check failed after 3 attempt(s): timed out")

    monkeypatch.setattr(IntegrationManager, "health_check", _failing_health_check)

    first = client.get(f"/api/v1/payers/{payer.id}/health-check")
    second = client.get(f"/api/v1/payers/{payer.id}/health-check")

    assert first.status_code == 200
    assert first.json()["status"] == "unhealthy"
    assert first.json()["failure_count"] == 1
    assert second.json()["failure_count"] == 2
    assert "timed out" in second.json()["error"]


def test_health_check_is_cross_tenant_safe(client, db, tenant):
    from app.models.organization import Organization
    from app.models.payer import Payer

    other = Organization(name="Other Hospital", email="other@hospital.test")
    db.add(other)
    db.flush()
    other_payer = Payer(organization_id=other.id, name="AAR", payer_code="AAR")
    db.add(other_payer)
    db.commit()

    response = client.get(f"/api/v1/payers/{other_payer.id}/health-check")

    assert response.status_code == 404
