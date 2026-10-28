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


def test_create_list_and_update_kenya_payer(client, db):
    from app.models.audit_log import AuditLog

    created = client.post(
        "/api/v1/payers",
        json={
            "name": "Social Health Authority",
            "payer_code": "sha",
            "submission_method": "portal",
            "status_method": "portal",
            "payment_method": "report",
            "portal_url": "https://portal.sha.go.ke",
            "supports_manual": True,
            "reason": "Configure Kenya launch payer",
        },
    )
    assert created.status_code == 201
    assert created.json()["payer_code"] == "SHA"
    assert created.json()["country"] == "KE"

    listed = client.get("/api/v1/payers")
    assert listed.status_code == 200
    assert [payer["id"] for payer in listed.json()] == [created.json()["id"]]

    updated = client.patch(
        f"/api/v1/payers/{created.json()['id']}",
        json={
            "payment_method": "excel",
            "reason": "Use SHA remittance workbook",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["payment_method"] == "excel"
    actions = {row.action for row in db.query(AuditLog).all()}
    assert actions == {"payer.created", "payer.updated"}


def test_create_payer_rejects_invalid_method_configuration(client):
    response = client.post(
        "/api/v1/payers",
        json={
            "name": "Jubilee Health",
            "payer_code": "JUBILEE",
            "submission_method": "email",
            "reason": "Configure email workflow",
        },
    )

    assert response.status_code == 422


def test_payer_integration_binding_is_cross_tenant_safe(client, db, tenant):
    from app.models.integration import Integration
    from app.models.organization import Organization

    other = Organization(name="Other Hospital", email="other@hospital.test")
    db.add(other)
    db.flush()
    integration = Integration(
        organization_id=other.id,
        provider="waystar",
        settings={"submission_connector": "mock"},
    )
    db.add(integration)
    db.commit()

    response = client.post(
        "/api/v1/payers",
        json={
            "name": "Britam Health",
            "payer_code": "BRITAM",
            "submission_method": "api",
            "status_method": "api",
            "payment_method": "api",
            "supports_api": True,
            "connector_name": "mock",
            "integration_id": integration.id,
            "reason": "Configure insurer API",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Integration not found"


def test_payer_get_is_cross_tenant_safe(client, db):
    from app.models.organization import Organization
    from app.models.payer import Payer

    other = Organization(name="Other Hospital", email="other2@hospital.test")
    db.add(other)
    db.flush()
    payer = Payer(organization_id=other.id, name="AAR", payer_code="AAR")
    db.add(payer)
    db.commit()

    response = client.get(f"/api/v1/payers/{payer.id}")

    assert response.status_code == 404
