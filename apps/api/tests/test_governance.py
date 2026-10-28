from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.governance.models import PatientConsent, RetentionPolicy, UserSession
from app.main import app
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user


@pytest.fixture
def governance_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    organization = Organization(name="Nairobi Hospital", email="grc@nairobi.test")
    other = Organization(name="Mombasa Hospital", email="grc@mombasa.test")
    db.add_all([organization, other])
    db.flush()
    admin = User(
        organization_id=organization.id,
        email="admin@nairobi.test",
        password_hash="x",
        first_name="Admin",
        last_name="One",
        role=UserRole.ADMIN,
    )
    auditor = User(
        organization_id=organization.id,
        email="audit@nairobi.test",
        password_hash="x",
        first_name="Audit",
        last_name="One",
        role=UserRole.AUDITOR,
    )
    viewer = User(
        organization_id=organization.id,
        email="viewer@nairobi.test",
        password_hash="x",
        first_name="View",
        last_name="One",
        role=UserRole.VIEWER,
    )
    other_admin = User(
        organization_id=other.id,
        email="admin@mombasa.test",
        password_hash="x",
        first_name="Admin",
        last_name="Two",
        role=UserRole.ADMIN,
    )
    own_patient = Patient(
        organization_id=organization.id,
        first_name="A",
        last_name="Patient",
        medical_record_number="NRB-1",
        date_of_birth=date(1990, 1, 1),
    )
    other_patient = Patient(
        organization_id=other.id,
        first_name="B",
        last_name="Patient",
        medical_record_number="MBA-1",
        date_of_birth=date(1991, 1, 1),
    )
    db.add_all([admin, auditor, viewer, other_admin, own_patient, other_patient])
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    yield db, client, organization, other, admin, auditor, viewer, own_patient, other_patient
    app.dependency_overrides.clear()
    db.close()


def test_consent_versions_are_append_only_and_cross_tenant_safe(governance_context):
    db, client, _, _, _, _, _, patient, other_patient = governance_context
    first = client.post(
        f"/api/v1/governance/patients/{patient.id}/consents",
        json={"purpose": "ai_processing", "decision": "granted", "reason": "Treatment workflow"},
    )
    second = client.post(
        f"/api/v1/governance/patients/{patient.id}/consents",
        json={"purpose": "ai_processing", "decision": "revoked", "reason": "Patient withdrew"},
    )
    forbidden = client.post(
        f"/api/v1/governance/patients/{other_patient.id}/consents",
        json={"purpose": "research", "decision": "granted", "reason": "Research consent"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert [first.json()["version"], second.json()["version"]] == [1, 2]
    assert forbidden.status_code == 404
    history = client.get(f"/api/v1/governance/patients/{patient.id}/consents").json()
    assert [entry["decision"] for entry in history] == ["revoked", "granted"]
    assert db.query(PatientConsent).count() == 2


def test_retention_policy_versions_and_compliance_rbac(governance_context):
    _, client, _, _, _, auditor, viewer, _, _ = governance_context
    for days in (2555, 3650):
        response = client.post(
            "/api/v1/governance/retention-policies",
            json={
                "resource_type": "audit_logs",
                "retention_days": days,
                "disposition": "archive",
                "reason": "Hospital policy update",
            },
        )
        assert response.status_code == 200
    policies = client.get("/api/v1/governance/retention-policies").json()
    assert [policy["version"] for policy in policies] == [2, 1]
    assert all(policy["enforcement_mode"] == "report_only" for policy in policies)

    app.dependency_overrides[get_current_user] = lambda: viewer
    assert client.get("/api/v1/governance/summary").status_code == 403
    app.dependency_overrides[get_current_user] = lambda: auditor
    summary = client.get("/api/v1/governance/summary")
    assert summary.status_code == 200
    assert summary.json()["configured_retention_policies"] == 1


def test_correlation_timeline_is_tenant_scoped_and_redacted(governance_context):
    db, client, organization, other, admin, _, _, _, _ = governance_context
    own = AuditService(db).log(
        organization_id=organization.id,
        user_id=admin.id,
        action=AuditAction.CLAIM_UPDATED,
        entity="claim",
        entity_id=948,
        correlation_id="claim-948",
        after_state={"status": "partial", "access_token": "secret"},
    )
    other_user = db.query(User).filter(User.organization_id == other.id).one()
    AuditService(db).log(
        organization_id=other.id,
        user_id=other_user.id,
        action=AuditAction.CLAIM_UPDATED,
        entity="claim",
        entity_id=948,
        correlation_id="claim-948",
    )
    db.commit()

    response = client.get("/api/v1/governance/audit/correlations/claim-948")
    assert response.status_code == 200
    assert [event["id"] for event in response.json()] == [own.id]
    assert response.json()[0]["after_state"]["access_token"] == "[REDACTED]"


def test_audit_rows_cannot_be_updated_or_deleted(governance_context):
    db, _, organization, _, admin, _, _, _, _ = governance_context
    entry = AuditService(db).log(
        organization_id=organization.id,
        user_id=admin.id,
        action=AuditAction.CLAIM_CREATED,
        entity="claim",
        entity_id=1,
    )
    db.commit()

    with pytest.raises(DatabaseError, match="immutable"):
        db.execute(
            text("UPDATE audit_logs SET action = 'changed' WHERE id = :id"), {"id": entry.id}
        )
        db.commit()
    db.rollback()
    with pytest.raises(DatabaseError, match="immutable"):
        db.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": entry.id})
        db.commit()


def test_retention_and_session_queries_exclude_other_tenants(governance_context):
    db, client, organization, other, admin, _, _, _, _ = governance_context
    other_admin = db.query(User).filter(User.organization_id == other.id).one()
    now = datetime.now(UTC)
    db.add_all(
        [
            RetentionPolicy(
                organization_id=other.id,
                resource_type="audit_logs",
                version=1,
                retention_days=3650,
                disposition="archive",
                legal_hold_default=False,
                enforcement_mode="report_only",
                created_by=other_admin.id,
                reason="Other tenant policy",
                correlation_id="other-policy",
                created_at=now,
            ),
            UserSession(
                id="other-session",
                organization_id=other.id,
                user_id=other_admin.id,
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            ),
            UserSession(
                id="own-session",
                organization_id=organization.id,
                user_id=admin.id,
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            ),
        ]
    )
    db.commit()

    assert client.get("/api/v1/governance/retention-policies").json() == []
    sessions = client.get("/api/v1/governance/sessions").json()
    assert [session["id"] for session in sessions] == ["own-session"]
    forbidden = client.post(
        "/api/v1/governance/sessions/other-session/revoke",
        json={"reason": "Attempted cross-tenant revocation"},
    )
    assert forbidden.status_code == 404
    assert db.get(UserSession, "other-session").revoked_at is None
