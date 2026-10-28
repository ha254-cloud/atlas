from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
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
    organization = Organization(name="Atlas Hospital", email="atlas@example.com", currency="KES")
    other_organization = Organization(
        name="Other Hospital", email="other@example.com", currency="USD"
    )
    db_session.add_all([organization, other_organization])
    db_session.flush()
    admin = User(
        organization_id=organization.id,
        email="admin@example.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    analyst = User(
        organization_id=organization.id,
        email="analyst@example.com",
        password_hash="x",
        first_name="Revenue",
        last_name="Analyst",
        role=UserRole.REVENUE_ANALYST,
    )
    foreign_admin = User(
        organization_id=other_organization.id,
        email="foreign@example.com",
        password_hash="x",
        first_name="Foreign",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-BRANCH",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=organization.id, name="SHA", payer_code="SHA")
    db_session.add_all([admin, analyst, foreign_admin, patient, payer])
    db_session.commit()
    return {
        "organization": organization,
        "other_organization": other_organization,
        "admin": admin,
        "analyst": analyst,
        "foreign_admin": foreign_admin,
        "patient": patient,
        "payer": payer,
    }


@pytest.fixture
def auth_context(seed):
    return {"organization_id": seed["organization"].id, "user": seed["admin"]}


@pytest.fixture
def client(db_session, auth_context):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_organization] = lambda: auth_context["organization_id"]
    app.dependency_overrides[get_current_user] = lambda: auth_context["user"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def _create_branch(client, name="Nairobi Hospital", code="NRB"):
    response = client.post(
        "/api/v1/branches",
        json={"name": name, "code": code, "reason": "Configure hospital branch"},
    )
    assert response.status_code == 201
    return response.json()


def test_branch_department_membership_are_tenant_scoped_and_audited(
    client, seed, db_session, auth_context
):
    branch = _create_branch(client)
    department_response = client.post(
        f"/api/v1/branches/{branch['id']}/departments",
        json={
            "name": "Revenue Cycle",
            "code": "RCM",
            "reason": "Configure operations",
        },
    )
    membership_response = client.post(
        f"/api/v1/branches/{branch['id']}/memberships",
        json={
            "user_id": seed["analyst"].id,
            "role_template": "Revenue Officer",
            "reason": "Assign branch operations",
        },
    )

    assert department_response.status_code == 201
    assert department_response.json()["organization_id"] == seed["organization"].id
    assert membership_response.status_code == 201
    auth_context["user"] = seed["analyst"]
    assert [row["id"] for row in client.get("/api/v1/branches").json()] == [branch["id"]]
    actions = {row.action for row in db_session.query(AuditLog).all()}
    assert {
        "branch.created",
        "department.created",
        "branch_membership.assigned",
    }.issubset(actions)


def test_branch_scoped_user_sees_only_assigned_claims_and_currency_snapshot(
    client, seed, auth_context
):
    assigned = _create_branch(client, "Nairobi Hospital", "NRB")
    other = _create_branch(client, "Mombasa Hospital", "MBA")
    client.post(
        f"/api/v1/branches/{assigned['id']}/memberships",
        json={
            "user_id": seed["analyst"].id,
            "role_template": "Revenue Officer",
            "reason": "Assign Nairobi claims",
        },
    )
    base_claim = {
        "patient_id": seed["patient"].id,
        "payer_id": seed["payer"].id,
        "billed_amount": 1000,
        "paid_amount": 0,
        "service_date": "2026-01-05",
    }
    first = client.post(
        "/api/v1/claims/",
        json={**base_claim, "claim_number": "NRB-1", "branch_id": assigned["id"]},
    )
    client.post(
        "/api/v1/claims/",
        json={**base_claim, "claim_number": "MBA-1", "branch_id": other["id"]},
    )
    assert first.status_code == 200
    assert first.json()["currency"] == "KES"

    auth_context["user"] = seed["analyst"]
    listed = client.get("/api/v1/claims/").json()
    assert [claim["claim_number"] for claim in listed] == ["NRB-1"]
    assert client.get(f"/api/v1/claims/{first.json()['id']}").status_code == 200
    denied = client.post(
        "/api/v1/claims/",
        json={**base_claim, "claim_number": "MBA-2", "branch_id": other["id"]},
    )
    assert denied.status_code == 404


def test_cross_tenant_branch_and_membership_assignment_are_hidden(client, seed, db_session):
    from app.branches.models import Branch

    foreign_branch = Branch(
        organization_id=seed["other_organization"].id,
        name="Foreign Branch",
        code="FOREIGN",
    )
    db_session.add(foreign_branch)
    db_session.commit()

    assert (
        client.patch(
            f"/api/v1/branches/{foreign_branch.id}",
            json={"name": "Compromised", "reason": "Cross-tenant attempt"},
        ).status_code
        == 404
    )
    local_branch_id = _create_branch(client, "Local Branch", "LOCAL")["id"]
    membership = client.post(
        f"/api/v1/branches/{local_branch_id}/memberships",
        json={
            "user_id": seed["foreign_admin"].id,
            "role_template": "Branch Manager",
            "reason": "Cross-tenant attempt",
        },
    )
    assert membership.status_code == 404


def test_canonical_import_preserves_branch_department_and_currency(db_session, seed):
    from app.branches.models import Branch, Department
    from app.processing.exceptions import PersistenceError
    from app.processing.processor import ClaimProcessor

    branch = Branch(
        organization_id=seed["organization"].id,
        name="Nairobi Hospital",
        code="NRB",
    )
    db_session.add(branch)
    db_session.flush()
    department = Department(
        organization_id=seed["organization"].id,
        branch_id=branch.id,
        name="Revenue Cycle",
        code="RCM",
    )
    db_session.add(department)
    db_session.commit()
    row = {
        "claim_number": "IMPORT-BRANCH-1",
        "medical_record_number": seed["patient"].medical_record_number,
        "payer_code": seed["payer"].payer_code,
        "billed_amount": "250.00",
        "paid_amount": "0.00",
        "service_date": "2026-01-10",
        "branch_code": "NRB",
        "department_code": "RCM",
        "currency": "USD",
    }

    claim = ClaimProcessor(db_session, seed["organization"].id).process(row)

    assert claim.branch_id == branch.id
    assert claim.department_id == department.id
    assert claim.currency == "USD"
    with pytest.raises(PersistenceError, match="Unknown branch code"):
        ClaimProcessor(db_session, seed["organization"].id).process(
            {**row, "claim_number": "IMPORT-BRANCH-2", "branch_code": "UNKNOWN"}
        )
