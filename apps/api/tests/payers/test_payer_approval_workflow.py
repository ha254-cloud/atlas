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
    submitter = User(
        organization_id=organization.id,
        email="biller@nairobi.test",
        password_hash="x",
        first_name="Biller",
        last_name="User",
        role=UserRole.MANAGER,
    )
    approver = User(
        organization_id=organization.id,
        email="manager@nairobi.test",
        password_hash="x",
        first_name="Manager",
        last_name="Approver",
        role=UserRole.MANAGER,
    )
    viewer = User(
        organization_id=organization.id,
        email="viewer@nairobi.test",
        password_hash="x",
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
    )
    db.add_all([submitter, approver, viewer])
    db.commit()
    return {
        "organization": organization,
        "submitter": submitter,
        "approver": approver,
        "viewer": viewer,
    }


@pytest.fixture()
def client(db, tenant):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: tenant["organization"].id
    app.dependency_overrides[get_current_user] = lambda: tenant["submitter"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def _create_payer(client, **overrides) -> dict:
    payload = {
        "name": "Social Health Authority",
        "payer_code": "sha",
        "submission_method": "manual",
        "status_method": "manual",
        "payment_method": "report",
        "reason": "Configure Kenya launch payer",
    }
    payload.update(overrides)
    response = client.post("/api/v1/payers", json=payload)
    assert response.status_code == 201
    return response.json()


def test_new_payer_starts_in_draft(client):
    payer = _create_payer(client)
    assert payer["approval_status"] == "draft"


def test_submit_approve_lifecycle(client, tenant, db):
    from app.models.audit_log import AuditLog

    payer = _create_payer(client)

    submitted = client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")
    assert submitted.status_code == 200
    assert submitted.json()["approval_status"] == "pending_approval"
    assert submitted.json()["submitted_by"] == tenant["submitter"].id

    as_user(tenant["approver"])
    approved = client.post(f"/api/v1/payers/{payer['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"
    assert approved.json()["approved_by"] == tenant["approver"].id

    actions = {row.action for row in db.query(AuditLog).all()}
    assert {
        "payer.created",
        "payer.submitted_for_approval",
        "payer.approved",
    } <= actions


def test_reject_requires_reason_and_records_it(client, tenant):
    payer = _create_payer(client)
    client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")

    as_user(tenant["approver"])
    missing_reason = client.post(f"/api/v1/payers/{payer['id']}/reject", json={})
    assert missing_reason.status_code == 422

    rejected = client.post(
        f"/api/v1/payers/{payer['id']}/reject",
        json={"reason": "Tariff schedule is missing required procedure codes"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == "rejected"
    assert rejected.json()["rejection_reason"] == (
        "Tariff schedule is missing required procedure codes"
    )


def test_rejected_payer_can_be_resubmitted(client, tenant):
    payer = _create_payer(client)
    client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")

    as_user(tenant["approver"])
    client.post(
        f"/api/v1/payers/{payer['id']}/reject",
        json={"reason": "Needs portal URL before approval"},
    )

    as_user(tenant["submitter"])
    resubmitted = client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")
    assert resubmitted.status_code == 200
    assert resubmitted.json()["approval_status"] == "pending_approval"
    # Resubmitting clears the prior rejection reason.
    assert resubmitted.json()["rejection_reason"] is None


def test_cannot_approve_own_submission(client, tenant):
    payer = _create_payer(client)
    client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")

    response = client.post(f"/api/v1/payers/{payer['id']}/approve")

    assert response.status_code == 400
    assert "same user" in response.json()["detail"]


def test_cannot_approve_a_draft_payer(client, tenant):
    payer = _create_payer(client)

    as_user(tenant["approver"])
    response = client.post(f"/api/v1/payers/{payer['id']}/approve")

    assert response.status_code == 400
    assert "draft" in response.json()["detail"]


def test_viewer_cannot_approve_payer(client, tenant):
    payer = _create_payer(client)
    client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")

    as_user(tenant["viewer"])
    response = client.post(f"/api/v1/payers/{payer['id']}/approve")

    assert response.status_code == 403


def test_viewer_cannot_submit_payer_for_approval(client, tenant):
    payer = _create_payer(client)

    as_user(tenant["viewer"])
    response = client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval")

    assert response.status_code == 403


def test_payer_approval_is_cross_tenant_safe(client, db, tenant):
    from app.models.organization import Organization
    from app.models.payer import Payer

    other = Organization(name="Other Hospital", email="other@hospital.test")
    db.add(other)
    db.flush()
    other_payer = Payer(
        organization_id=other.id,
        name="AAR",
        payer_code="AAR",
        approval_status="pending_approval",
    )
    db.add(other_payer)
    db.commit()

    response = client.post(f"/api/v1/payers/{other_payer.id}/approve")

    assert response.status_code == 404
