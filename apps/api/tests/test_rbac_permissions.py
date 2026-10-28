"""
API-level tests for the RBAC/permission system introduced in the Enterprise
Security Sprint: Permission enum + ROLE_PERMISSIONS mapping +
require_permission() dependency, wired into claims/appeals/audit-log
endpoints. Uses the same TestClient + SQLite in-memory + dependency-override
pattern as test_claim_api.py.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.audit.actions import AuditAction
from app.audit.service import AuditService
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
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.user import User, UserRole

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    other_org = Organization(name="Other Health System", email="other@atlasdemo.com")
    db_session.add_all([org, other_org])
    db_session.flush()

    patient = Patient(
        organization_id=org.id,
        first_name="John",
        last_name="Smith",
        medical_record_number="MRN-001",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Aetna", payer_code="AETNA")
    admin = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    viewer = User(
        organization_id=org.id,
        email="viewer@atlasdemo.com",
        password_hash="x",
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
    )
    auditor = User(
        organization_id=org.id,
        email="auditor@atlasdemo.com",
        password_hash="x",
        first_name="Audit",
        last_name="Or",
        role=UserRole.AUDITOR,
    )
    db_session.add_all([patient, payer, admin, viewer, auditor])
    db_session.commit()

    return {
        "org": org,
        "other_org": other_org,
        "patient": patient,
        "payer": payer,
        "admin": admin,
        "viewer": viewer,
        "auditor": auditor,
    }


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["admin"]

    yield TestClient(app)

    app.dependency_overrides.clear()


def as_user(user):
    """Switch the shared dependency-override to a different acting user
    for the next request(s) made against `client`. app.dependency_overrides
    is global app state (not per-TestClient), so role-switching within a
    single test must mutate it directly rather than using separate
    per-role client fixtures side by side."""
    app.dependency_overrides[get_current_user] = lambda: user


def _claim_payload(seed, **overrides):
    payload = {
        "patient_id": seed["patient"].id,
        "payer_id": seed["payer"].id,
        "claim_number": "CLM-0001",
        "billed_amount": 1500.00,
        "paid_amount": 0.00,
        "service_date": "2026-01-05",
    }
    payload.update(overrides)
    return payload


def test_viewer_can_list_claims(client, seed):
    as_user(seed["viewer"])
    response = client.get("/api/v1/claims/")
    assert response.status_code == 200


def test_viewer_cannot_create_claim(client, seed):
    as_user(seed["viewer"])
    response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    assert response.status_code == 403


def test_admin_can_create_claim(client, seed):
    response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    assert response.status_code == 200


def test_viewer_cannot_delete_claim(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    as_user(seed["viewer"])
    response = client.delete(f"/api/v1/claims/{created['id']}")
    assert response.status_code == 403


def test_claim_creation_is_audit_logged(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    as_user(seed["auditor"])
    logs = client.get("/api/v1/audit-logs").json()
    actions = [entry["action"] for entry in logs]
    assert "claim.created" in actions

    created_entry = next(e for e in logs if e["action"] == "claim.created")
    assert created_entry["entity_id"] == created["id"]


def test_viewer_cannot_view_audit_log(client, seed):
    as_user(seed["viewer"])
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 403


def test_auditor_can_view_audit_log(client, seed):
    as_user(seed["auditor"])
    response = client.get("/api/v1/audit-logs")
    assert response.status_code == 200


def test_audit_log_returns_change_reason_and_correlation(client, db_session, seed):
    AuditService(db_session).log(
        organization_id=seed["org"].id,
        user_id=seed["admin"].id,
        action=AuditAction.CLAIM_UPDATED,
        entity="claim",
        entity_id=948,
        reason="Correct insurer response",
        correlation_id="claim-948-review",
        before_state={"status": "submitted"},
        after_state={"status": "partially_paid"},
        user_agent="Chrome",
        device="desktop",
    )
    db_session.commit()

    as_user(seed["auditor"])
    response = client.get("/api/v1/audit-logs")

    assert response.status_code == 200
    event = response.json()[0]
    assert event["correlation_id"] == "claim-948-review"
    assert event["reason"] == "Correct insurer response"
    assert event["before_state"] == {"status": "submitted"}
    assert event["after_state"] == {"status": "partially_paid"}
    assert event["device"] == "desktop"


def test_organization_get_allows_own_org(client, seed):
    response = client.get(f"/api/v1/organizations/{seed['org'].id}")
    assert response.status_code == 200


def test_organization_get_blocks_other_org(client, seed):
    response = client.get(f"/api/v1/organizations/{seed['other_org'].id}")
    assert response.status_code == 404
