"""
API tests for the Integrations router — connect/list/sync/disconnect and
the health-check endpoint. Uses FastAPI TestClient with dependency
overrides (SQLite in-memory DB + fake auth), matching the pattern used by
test_claim_api.py.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import Base, get_db
from app.core.dependencies import get_current_organization
from app.security.dependencies import get_current_user
from app import models as _models  # noqa: F401 — registers every model on Base.metadata


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
    from app.models.organization import Organization
    from app.models.user import User, UserRole

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    db_session.add(org)
    db_session.flush()

    user = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    return {"org": org, "user": user}


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_list_integrations_requires_auth():
    client = TestClient(app)
    response = client.get("/api/v1/integrations")
    assert response.status_code == 401


def test_list_providers_returns_registered_connectors(client):
    response = client.get("/api/v1/integrations/providers")
    assert response.status_code == 200
    providers = response.json()
    assert "epic" in providers
    assert "athena" in providers
    assert "sftp" in providers


def test_create_sftp_requires_connection_details(client):
    response = client.post("/api/v1/integrations", json={"provider": "sftp"})
    assert response.status_code == 422


def test_create_sftp_encrypts_password(client, db_session):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.models.integration import Integration

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        response = client.post(
            "/api/v1/integrations",
            json={
                "provider": "sftp",
                "settings": {
                    "hostname": "sftp.hospital.test",
                    "username": "atlas",
                    "remote_path": "/claims",
                    "host_key_sha256": "SHA256:test-fingerprint",
                },
                "access_token": "secret-password",
            },
        )
        assert response.status_code == 201
        row = db_session.get(Integration, response.json()["id"])
        assert row.encrypted_access_token != "secret-password"
        assert "password" not in row.settings
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_connector_claim_uses_canonical_patient_payer_and_workflow(db_session, seed):
    from datetime import date
    from decimal import Decimal

    from app.canonical.claim import CanonicalClaim
    from app.imports.claim_import_service import ClaimImportService
    from app.models.claim_workflow import ClaimWorkflow

    claim = ClaimImportService(db_session, seed["org"].id).import_canonical(CanonicalClaim(
        claim_number="CLM-CONNECTOR-001",
        patient_first_name="Amina",
        patient_last_name="Wanjiku",
        patient_mrn="MRN-CONNECTOR-001",
        payer_code="AETNA",
        billed_amount=Decimal("125000"),
        paid_amount=Decimal("0"),
        service_date=date(2026, 7, 15),
        status="denied",
    ))

    assert claim.patient_id > 0
    assert claim.payer_id > 0
    assert claim.patient.first_name == "Amina"
    assert claim.payer.payer_code == "AETNA"
    assert db_session.query(ClaimWorkflow).filter_by(claim_id=claim.id).one()


def test_create_integration_rejects_unknown_provider(client):
    response = client.post("/api/v1/integrations", json={"provider": "not_a_real_ehr"})
    assert response.status_code == 400


def test_create_integration_succeeds_and_never_exposes_tokens(client):
    response = client.post(
        "/api/v1/integrations",
        json={"provider": "epic", "settings": {"base_url": "https://example.org"}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "epic"
    assert body["status"] == "pending"
    assert "access_token" not in body
    assert "encrypted_access_token" not in body


def test_list_and_get_integration(client):
    created = client.post("/api/v1/integrations", json={"provider": "athena"}).json()

    listed = client.get("/api/v1/integrations").json()
    assert any(i["id"] == created["id"] for i in listed)

    fetched = client.get(f"/api/v1/integrations/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["provider"] == "athena"


def test_get_integration_404_for_unknown_id(client):
    response = client.get("/api/v1/integrations/99999")
    assert response.status_code == 404


def test_disconnect_clears_tokens_and_sets_status(client, db_session):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.models.integration import Integration

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        created = client.post(
            "/api/v1/integrations",
            json={"provider": "epic", "access_token": "should-be-cleared"},
        ).json()

        response = client.post(f"/api/v1/integrations/{created['id']}/disconnect")
        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"

        row = db_session.query(Integration).get(created["id"])
        assert row.encrypted_access_token is None
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_trigger_sync_enqueues_celery_task(client):
    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()

    with patch("app.workers.tasks.sync_integration.delay") as mock_delay:
        response = client.post(f"/api/v1/integrations/{created['id']}/sync")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    mock_delay.assert_called_once()


def test_audit_log_entries_created_for_connect_sync_disconnect(client, db_session):
    from app.models.audit_log import AuditLog

    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()

    with patch("app.workers.tasks.sync_integration.delay"):
        client.post(f"/api/v1/integrations/{created['id']}/sync")

    client.post(f"/api/v1/integrations/{created['id']}/disconnect")

    actions = {
        row.action
        for row in db_session.query(AuditLog).filter(AuditLog.entity_id == created["id"]).all()
    }
    assert "integration.connected" in actions
    assert "integration.sync_triggered" in actions
    assert "integration.disconnected" in actions


def test_health_check_reports_disconnected_when_no_token(client):
    """Epic's connector requires an access token to authenticate — creating
    one without a token (no OAuth flow completed yet) should surface as a
    clear, non-crashing "not connected" health result."""
    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()

    response = client.get(f"/api/v1/integrations/{created['id']}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["last_error"]


def test_create_integration_encrypts_tokens(client, db_session):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.models.integration import Integration

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        created = client.post(
            "/api/v1/integrations",
            json={"provider": "epic", "access_token": "super-secret-token"},
        ).json()

        row = db_session.query(Integration).get(created["id"])
        assert row.encrypted_access_token is not None
        assert row.encrypted_access_token != "super-secret-token"
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_typed_credentials_create_append_only_version_without_secret(client, db_session):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.models.integration import IntegrationCredentialVersion

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        response = client.post(
            "/api/v1/integrations",
            json={
                "provider": "epic",
                "credentials": {
                    "kind": "oauth2",
                    "access_token": "typed-secret",
                    "expires_at": "2026-08-02T12:00:00Z",
                },
            },
        )
        assert response.status_code == 201

        versions = client.get(
            f"/api/v1/integrations/{response.json()['id']}/credentials/versions"
        )
        assert versions.status_code == 200
        assert versions.json()[0]["version"] == 1
        assert versions.json()[0]["credential_kind"] == "oauth2"
        assert "typed-secret" not in versions.text

        stored = db_session.query(IntegrationCredentialVersion).one()
        assert stored.fingerprints["primary"]
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_rotate_credentials_replaces_current_secret_and_audits_fingerprints(
    client,
    db_session,
):
    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.integrations.encryption import decrypt_token
    from app.models.audit_log import AuditLog
    from app.models.integration import Integration, IntegrationCredentialVersion

    original_key = settings.INTEGRATION_ENCRYPTION_KEY
    settings.INTEGRATION_ENCRYPTION_KEY = Fernet.generate_key().decode()
    try:
        created = client.post(
            "/api/v1/integrations",
            json={
                "provider": "waystar",
                "credentials": {"kind": "api_key", "api_key": "old-api-key"},
            },
        ).json()

        response = client.post(
            f"/api/v1/integrations/{created['id']}/credentials/rotate",
            json={
                "credentials": {"kind": "api_key", "api_key": "new-api-key"},
                "reason": "Scheduled security rotation",
            },
        )

        assert response.status_code == 200
        assert response.json()["version"] == 2
        row = db_session.get(Integration, created["id"])
        assert decrypt_token(row.encrypted_access_token) == "new-api-key"
        assert db_session.query(IntegrationCredentialVersion).count() == 2
        audit = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "integration.credentials_rotated")
            .one()
        )
        assert audit.metadata_json["before"] != audit.metadata_json["after"]
        assert "api-key" not in str(audit.metadata_json)
    finally:
        settings.INTEGRATION_ENCRYPTION_KEY = original_key


def test_rotate_credentials_rejects_wrong_provider_contract(client):
    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()

    response = client.post(
        f"/api/v1/integrations/{created['id']}/credentials/rotate",
        json={
            "credentials": {"kind": "api_key", "api_key": "wrong-kind"},
            "reason": "Test invalid contract",
        },
    )

    assert response.status_code == 422


def test_expired_credentials_block_health_check(client, db_session):
    from app.models.integration import Integration

    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()
    row = db_session.get(Integration, created["id"])
    row.token_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    response = client.get(f"/api/v1/integrations/{created['id']}/health")

    assert response.status_code == 200
    assert response.json()["connected"] is False
    assert "expired" in response.json()["last_error"].lower()


def test_credential_versions_and_rotation_deny_cross_tenant_access(
    client,
    db_session,
    seed,
):
    from app.core.dependencies import get_current_organization
    from app.models.organization import Organization
    from app.models.user import User, UserRole
    from app.security.dependencies import get_current_user

    created = client.post("/api/v1/integrations", json={"provider": "epic"}).json()
    other_org = Organization(name="Other Hospital", email="other@hospital.test")
    db_session.add(other_org)
    db_session.flush()
    other_user = User(
        organization_id=other_org.id,
        email="admin@other.test",
        password_hash="x",
        first_name="Other",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(other_user)
    db_session.commit()
    app.dependency_overrides[get_current_organization] = lambda: other_org.id
    app.dependency_overrides[get_current_user] = lambda: other_user

    versions = client.get(
        f"/api/v1/integrations/{created['id']}/credentials/versions"
    )
    rotation = client.post(
        f"/api/v1/integrations/{created['id']}/credentials/rotate",
        json={
            "credentials": {"kind": "oauth2", "access_token": "cross-tenant"},
            "reason": "Cross tenant attempt",
        },
    )

    assert versions.status_code == 404
    assert rotation.status_code == 404
