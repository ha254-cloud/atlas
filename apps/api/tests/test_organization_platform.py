from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.audit.actions import AuditAction
from app.billing.models import RecoveryFeeSchedule
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization, OrganizationSettingsVersion
from app.models.user import User, UserRole
from app.organizations.schemas import OrganizationSettings
from app.security.dependencies import get_current_user


@pytest.fixture
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


@pytest.fixture
def seed(db_session):
    organization = Organization(
        name="Atlas Hospital",
        slug="atlas-hospital",
        email="admin@atlas.example",
        billing_email="billing@atlas.example",
        timezone="UTC",
        currency="USD",
        settings={},
    )
    other_organization = Organization(
        name="Other Hospital",
        slug="other-hospital",
        email="admin@other.example",
        timezone="UTC",
        currency="USD",
        settings={},
    )
    db_session.add_all([organization, other_organization])
    db_session.flush()
    admin = User(
        organization_id=organization.id,
        email="owner@atlas.example",
        password_hash="x",
        first_name="Atlas",
        last_name="Owner",
        role=UserRole.ADMIN,
    )
    viewer = User(
        organization_id=organization.id,
        email="viewer@atlas.example",
        password_hash="x",
        first_name="Atlas",
        last_name="Viewer",
        role=UserRole.VIEWER,
    )
    db_session.add_all([admin, viewer])
    db_session.commit()
    return {
        "organization": organization,
        "other_organization": other_organization,
        "admin": admin,
        "viewer": viewer,
    }


@pytest.fixture
def client(db_session, seed):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_organization] = lambda: seed["organization"].id
    app.dependency_overrides[get_current_user] = lambda: seed["admin"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def _settings(**feature_overrides):
    settings = OrganizationSettings()
    return settings.model_copy(
        update={
            "features": settings.features.model_copy(update=feature_overrides),
            "billing": settings.billing.model_copy(
                update={
                    "success_fee_percentage": Decimal("12.50"),
                    "currency": "KES",
                    "vat_percentage": Decimal("16.00"),
                }
            ),
        }
    ).model_dump(mode="json")


def test_get_settings_returns_typed_defaults(client):
    response = client.get("/api/v1/organizations/current/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 0
    assert body["settings"]["workflow"]["require_approval"] is True
    assert body["settings"]["features"]["copilot"] is True


def test_admin_update_versions_settings_and_records_audit(client, db_session, seed):
    response = client.put(
        "/api/v1/organizations/current/settings",
        json={
            "settings": _settings(copilot=True, analytics=False),
            "reason": "Enable contracted enterprise package",
        },
        headers={"user-agent": "atlas-platform-test"},
    )

    assert response.status_code == 200
    assert response.json()["version"] == 1
    db_session.refresh(seed["organization"])
    assert seed["organization"].currency == "KES"
    assert str(seed["organization"].success_fee_percentage) == "12.50"
    version = db_session.query(OrganizationSettingsVersion).one()
    assert version.organization_id == seed["organization"].id
    assert version.settings["features"]["copilot"] is True
    fee_schedule = db_session.query(RecoveryFeeSchedule).one()
    assert fee_schedule.organization_id == seed["organization"].id
    assert str(fee_schedule.fee_percentage) == "12.50"
    assert str(fee_schedule.vat_percentage) == "16.00"
    assert fee_schedule.currency == "KES"
    assert fee_schedule.payment_terms_days == 30
    assert fee_schedule.dispute_period_days == 0
    audit = db_session.query(AuditLog).one()
    assert audit.action == AuditAction.ORGANIZATION_SETTINGS_UPDATED
    assert audit.organization_id == seed["organization"].id
    assert audit.metadata_json["reason"] == "Enable contracted enterprise package"
    assert audit.metadata_json["before"]["features"]["analytics"] is True
    assert audit.metadata_json["after"]["features"]["copilot"] is True
    assert audit.metadata_json["after"]["features"]["analytics"] is False
    assert audit.metadata_json["user_agent"] == "atlas-platform-test"


def test_settings_history_is_scoped_to_current_organization(client, db_session, seed):
    db_session.add_all(
        [
            OrganizationSettingsVersion(
                organization_id=seed["organization"].id,
                version=1,
                settings=_settings(copilot=True),
                changed_by=seed["admin"].id,
                reason="Tenant contract",
                correlation_id="tenant-version",
            ),
            OrganizationSettingsVersion(
                organization_id=seed["other_organization"].id,
                version=1,
                settings=_settings(portal_automation=True),
                changed_by=seed["admin"].id,
                reason="Other tenant contract",
                correlation_id="other-version",
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/organizations/current/settings/history")

    assert response.status_code == 200
    assert [row["correlation_id"] for row in response.json()] == ["tenant-version"]


def test_viewer_cannot_update_organization_settings(client, seed):
    app.dependency_overrides[get_current_user] = lambda: seed["viewer"]

    response = client.put(
        "/api/v1/organizations/current/settings",
        json={"settings": _settings(), "reason": "Unauthorized change"},
    )

    assert response.status_code == 403


def test_cross_tenant_organization_is_concealed(client, seed):
    response = client.get(f"/api/v1/organizations/{seed['other_organization'].id}")

    assert response.status_code == 404


def test_human_approval_cannot_be_disabled(client):
    settings = _settings()
    settings["workflow"]["require_approval"] = False

    response = client.put(
        "/api/v1/organizations/current/settings",
        json={"settings": settings, "reason": "Attempt automatic submission"},
    )

    assert response.status_code == 422


def test_disabled_feature_blocks_tenant_api(client, db_session, seed):
    seed["organization"].settings = _settings(analytics=False)
    db_session.commit()

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 403
    assert response.json()["detail"] == ("Feature 'analytics' is not enabled for this organization")
