"""
Tests for the Recovery Workflow Engine (app/workflows/): claim creation
auto-starts a ClaimWorkflow at VALIDATED, illegal transitions are rejected,
the ANALYZED auto-router branches correctly based on required documents,
permission gating matches the rest of the RBAC sprint, and the escalation
sweep flags overdue stages. Uses the same TestClient + SQLite in-memory +
dependency-override pattern as test_rbac_permissions.py.
"""

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
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
    db_session.add(org)
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
    db_session.add_all([patient, payer, admin, viewer])
    db_session.commit()

    return {
        "org": org,
        "patient": patient,
        "payer": payer,
        "admin": admin,
        "viewer": viewer,
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


def test_claim_creation_starts_workflow_at_validated(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    response = client.get(f"/api/v1/workflows/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "validated"
    assert body["previous_state"] == "imported"
    assert body["due_at"] is not None


def test_invalid_transition_is_rejected(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    response = client.post(
        f"/api/v1/workflows/{created['id']}/transition",
        json={"to_state": "recovered"},
    )
    assert response.status_code == 409


def test_analyzed_with_no_denial_routes_to_ready_for_appeal(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    response = client.post(
        f"/api/v1/workflows/{created['id']}/transition",
        json={"to_state": "analyzed", "reason": "AI analysis completed"},
    )
    assert response.status_code == 200
    # No denial on file -> nothing to auto-route to WAITING_FOR_DOCUMENTS.
    assert response.json()["state"] == "ready_for_appeal"


def test_analyzed_with_required_documents_routes_to_waiting_for_documents(client, seed, db_session):
    from app.models.denial import Denial, DenialType
    from app.models.denial_code import DenialCode

    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    db_session.add(
        DenialCode(
            code="CO50",
            category=DenialType.MEDICAL_NECESSITY,
            description="Medical necessity denial",
            recovery_strategy="Submit medical records",
            required_documents=["medical_records", "physician_notes"],
        )
    )
    db_session.add(
        Denial(
            organization_id=seed["org"].id,
            claim_id=created["id"],
            denial_code="CO50",
            denial_type=DenialType.MEDICAL_NECESSITY,
            description="Not medically necessary",
        )
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/workflows/{created['id']}/transition",
        json={"to_state": "analyzed"},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "waiting_for_documents"


def test_viewer_cannot_transition_workflow(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    as_user(seed["viewer"])
    response = client.post(
        f"/api/v1/workflows/{created['id']}/transition",
        json={"to_state": "analyzed"},
    )
    assert response.status_code == 403


def test_viewer_can_view_workflow(client, seed):
    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()

    as_user(seed["viewer"])
    response = client.get(f"/api/v1/workflows/{created['id']}")
    assert response.status_code == 200


def test_work_queue_returns_claim_for_admin_high_value(client, seed):
    client.post("/api/v1/claims/", json=_claim_payload(seed, billed_amount=50000.00))

    response = client.get("/api/v1/workflows/queue")
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "High Value Claims"
    assert body["count"] == 1


def test_staff_work_queue_only_returns_assigned_claims(client, seed):
    own = client.post(
        "/api/v1/claims/",
        json=_claim_payload(
            seed,
            claim_number="CLM-OWN",
            assigned_user_id=seed["viewer"].id,
        ),
    ).json()
    client.post(
        "/api/v1/claims/",
        json=_claim_payload(
            seed,
            claim_number="CLM-OTHER",
            assigned_user_id=seed["admin"].id,
        ),
    )

    as_user(seed["viewer"])
    response = client.get("/api/v1/workflows/queue")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["claim_id"] == own["id"]
    assert response.json()["items"][0]["assigned_user_id"] == seed["viewer"].id


def test_manager_queue_summary_counts_current_work(client, seed):
    client.post(
        "/api/v1/claims/",
        json=_claim_payload(seed, assigned_user_id=seed["viewer"].id),
    )

    response = client.get("/api/v1/workflows/queue/summary")

    assert response.status_code == 200
    assert response.json() == {
        "assigned": 1,
        "pending": 1,
        "completed": 0,
        "overdue": 0,
    }


def test_escalation_sweep_flags_overdue_under_review(client, seed, db_session):
    from app.models.claim_workflow import ClaimWorkflow, ClaimWorkflowState

    created = client.post("/api/v1/claims/", json=_claim_payload(seed)).json()
    client.post(f"/api/v1/workflows/{created['id']}/transition", json={"to_state": "analyzed"})

    workflow = (
        db_session.query(ClaimWorkflow).filter(ClaimWorkflow.claim_id == created["id"]).first()
    )
    # Force it into UNDER_REVIEW with a deadline that's already passed.
    workflow.state = ClaimWorkflowState.UNDER_REVIEW
    workflow.due_at = datetime.utcnow() - timedelta(hours=1)
    workflow.escalated = False
    db_session.commit()

    response = client.post("/api/v1/workflows/escalate-sweep")
    assert response.status_code == 200
    body = response.json()
    assert body["escalated_count"] == 1
    assert created["id"] in body["claim_ids"]

    db_session.refresh(workflow)
    assert workflow.escalated is True
