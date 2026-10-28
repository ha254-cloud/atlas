"""
API-level tests for the Claims endpoints — auth wiring, query-param
filters, and the timeline endpoint. Uses FastAPI TestClient with
dependency overrides (SQLite in-memory DB + fake auth) — no real
PostgreSQL or JWT required.
"""

import csv
import io
from datetime import date

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
    # StaticPool keeps a single physical connection alive across threads —
    # FastAPI's TestClient runs endpoint code in a worker thread, and a
    # plain `:memory:` engine would otherwise hand that thread a brand new
    # (empty) SQLite database.
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
    user = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add_all([patient, payer, user])
    db_session.commit()

    return {"org": org, "patient": patient, "payer": payer, "user": user}


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]

    yield TestClient(app)

    app.dependency_overrides.clear()


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


def test_list_claims_requires_auth():
    # No dependency overrides installed on this client — auth must be enforced.
    client = TestClient(app)
    response = client.get("/api/v1/claims/")
    assert response.status_code == 401


def test_create_and_get_claim(client, seed):
    response = client.post("/api/v1/claims/", json=_claim_payload(seed, priority="high"))
    assert response.status_code == 200
    body = response.json()
    assert body["claim_number"] == "CLM-0001"
    assert body["priority"] == "high"
    assert body["organization_id"] == seed["org"].id

    get_response = client.get(f"/api/v1/claims/{body['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_export_claims_is_canonical_tenant_scoped_and_audited(client, seed, db_session):
    from app.canonical.normalizers.csv import CSVNormalizer
    from app.models.audit_log import AuditLog
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer

    client.post("/api/v1/claims/", json=_claim_payload(seed, status="denied"))
    foreign_org = Organization(name="Foreign Hospital", email="foreign@example.com")
    db_session.add(foreign_org)
    db_session.flush()
    foreign_patient = Patient(
        organization_id=foreign_org.id,
        first_name="Foreign",
        last_name="Patient",
        medical_record_number="FOREIGN-MRN",
        date_of_birth=date(1990, 1, 1),
    )
    foreign_payer = Payer(
        organization_id=foreign_org.id,
        name="Foreign Payer",
        payer_code="FOREIGN",
    )
    db_session.add_all([foreign_patient, foreign_payer])
    db_session.flush()
    db_session.add(
        Claim(
            organization_id=foreign_org.id,
            patient_id=foreign_patient.id,
            payer_id=foreign_payer.id,
            claim_number="FOREIGN-CLAIM",
            status="imported",
            billed_amount=500,
            paid_amount=0,
            service_date=date(2026, 1, 6),
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/claims/export.csv",
        params={"reason": "Authorized portability test"},
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert len(rows) == 1
    assert rows[0] == {
        "claim_number": "CLM-0001",
        "patient_first_name": "John",
        "patient_last_name": "Smith",
        "medical_record_number": "MRN-001",
        "payer_code": "AETNA",
        "branch_code": "",
        "department_code": "",
        "currency": "KES",
        "billed_amount": "1500.00",
        "paid_amount": "0.00",
        "service_date": "2026-01-05",
        "status": "denied",
        "diagnosis_codes": "",
        "procedure_codes": "",
    }
    canonical = CSVNormalizer().normalize(rows[0])
    assert canonical.claim_number == "CLM-0001"
    assert canonical.patient_mrn == "MRN-001"
    assert canonical.payer_code == "AETNA"
    assert canonical.currency == "KES"
    assert str(canonical.billed_amount) == "1500.00"
    assert canonical.service_date == date(2026, 1, 5)
    audit = db_session.query(AuditLog).filter(AuditLog.action == "claims.exported").one()
    assert audit.organization_id == seed["org"].id
    assert audit.user_id == seed["user"].id
    assert audit.reason == "Authorized portability test"
    assert audit.metadata_json == {"format": "csv", "row_count": 1}
    assert audit.correlation_id == response.headers["X-Request-ID"]


def test_export_claims_neutralizes_spreadsheet_formulas(client, seed, db_session):
    seed["patient"].first_name = "=HYPERLINK"
    db_session.commit()
    client.post("/api/v1/claims/", json=_claim_payload(seed))

    response = client.get(
        "/api/v1/claims/export.csv",
        params={"reason": "Formula safety validation"},
    )

    row = next(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert row["patient_first_name"] == "'=HYPERLINK"


def test_export_claims_requires_reason(client):
    response = client.get("/api/v1/claims/export.csv")
    assert response.status_code == 422


def test_export_claims_requires_narrow_permission(client, seed, db_session):
    from app.models.user import UserRole

    seed["user"].role = UserRole.VIEWER
    db_session.commit()

    response = client.get(
        "/api/v1/claims/export.csv",
        params={"reason": "Viewer export attempt"},
    )
    assert response.status_code == 403


def test_get_missing_claim_returns_404(client):
    response = client.get("/api/v1/claims/999999")
    assert response.status_code == 404


def test_list_claims_filters_by_priority(client, seed):
    client.post("/api/v1/claims/", json=_claim_payload(seed, claim_number="A", priority="high"))
    client.post("/api/v1/claims/", json=_claim_payload(seed, claim_number="B", priority="low"))

    response = client.get("/api/v1/claims/", params={"priority": "high"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["priority"] == "high"


def test_list_claims_filters_by_status(client, seed):
    client.post("/api/v1/claims/", json=_claim_payload(seed, claim_number="A", status="denied"))
    client.post("/api/v1/claims/", json=_claim_payload(seed, claim_number="B", status="paid"))

    response = client.get("/api/v1/claims/", params={"status": "denied"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["status"] == "denied"


def test_update_claim_status_triggers_timeline_event(client, seed):
    create_response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    claim_id = create_response.json()["id"]

    patch_response = client.patch(f"/api/v1/claims/{claim_id}", json={"status": "denied"})
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "denied"

    timeline_response = client.get(f"/api/v1/claims/{claim_id}/timeline")
    assert timeline_response.status_code == 200
    events = timeline_response.json()
    # CREATED, then the workflow engine's auto IMPORTED->VALIDATED
    # transition, then the manual status change from the PATCH above.
    assert len(events) == 3
    assert events[0]["event_type"] == "claim.created"
    assert events[-1]["event_type"] == "claim.status_changed"
    assert events[-1]["metadata"] == {"from": "imported", "to": "denied"}


def test_update_claim_records_mutation_evidence(client, seed, db_session):
    from app.models.audit_log import AuditLog

    create_response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    claim_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/claims/{claim_id}",
        json={"status": "denied", "reason": "Corrected after payer response"},
    )

    assert response.status_code == 200
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "claim.updated", AuditLog.entity_id == claim_id)
        .one()
    )
    assert audit.organization_id == seed["org"].id
    assert audit.user_id == seed["user"].id
    assert audit.reason == "Corrected after payer response"
    assert audit.before_state == {"status": "imported"}
    assert audit.after_state == {"status": "denied"}
    assert audit.metadata_json == {"changed_fields": ["status"]}
    assert audit.correlation_id == response.headers["X-Request-ID"]


def test_delete_claim(client, seed):
    create_response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    claim_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/v1/claims/{claim_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    get_response = client.get(f"/api/v1/claims/{claim_id}")
    assert get_response.status_code == 404


def test_create_claim_duplicate_claim_number_returns_400(client, seed):
    client.post("/api/v1/claims/", json=_claim_payload(seed))
    response = client.post("/api/v1/claims/", json=_claim_payload(seed))
    assert response.status_code == 400
