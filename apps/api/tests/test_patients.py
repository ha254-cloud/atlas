from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.events.bus import event_bus
from app.events.event_types import EventType
from app.main import app
from app.models.audit_log import AuditLog
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user


@pytest.fixture()
def patient_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    organization = Organization(name="Atlas Hospital", email="atlas@example.com")
    other_organization = Organization(name="Other Hospital", email="other@example.com")
    session.add_all([organization, other_organization])
    session.flush()

    user = User(
        organization_id=organization.id,
        email="analyst@atlas.example",
        password_hash="x",
        first_name="Revenue",
        last_name="Analyst",
        role=UserRole.REVENUE_ANALYST,
    )
    session.add_all(
        [
            user,
            Patient(
                organization_id=organization.id,
                first_name="Amina",
                last_name="Wanjiku",
                medical_record_number="MRN-100",
                date_of_birth=date(1988, 5, 12),
            ),
            Patient(
                organization_id=other_organization.id,
                first_name="Hidden",
                last_name="Patient",
                medical_record_number="MRN-OTHER",
                date_of_birth=date(1990, 1, 1),
            ),
        ]
    )
    session.commit()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    app.dependency_overrides[get_current_user] = lambda: user

    yield {
        "client": TestClient(app),
        "session": session,
        "organization": organization,
        "other_organization": other_organization,
        "user": user,
    }

    app.dependency_overrides.clear()
    session.close()


def test_list_patients_is_tenant_scoped_and_searchable(patient_context) -> None:
    response = patient_context["client"].get("/api/v1/patients", params={"search": "MRN-100"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": response.json()[0]["id"],
            "first_name": "Amina",
            "last_name": "Wanjiku",
            "medical_record_number": "MRN-100",
            "date_of_birth": "1988-05-12",
            "created_at": response.json()[0]["created_at"],
            "updated_at": response.json()[0]["updated_at"],
        }
    ]


def test_list_patients_preserves_legacy_record_without_mrn(patient_context) -> None:
    legacy_patient = Patient(
        organization_id=patient_context["organization"].id,
        first_name="Legacy",
        last_name="Import",
        medical_record_number="",
        date_of_birth=date(1900, 1, 1),
    )
    patient_context["session"].add(legacy_patient)
    patient_context["session"].commit()

    response = patient_context["client"].get("/api/v1/patients", params={"search": "Legacy"})

    assert response.status_code == 200
    assert response.json()[0]["id"] == legacy_patient.id
    assert response.json()[0]["medical_record_number"] == ""


def test_create_and_update_patient_records_audit_and_safe_events(patient_context) -> None:
    captured_events = []

    def capture_event(event_type: str, payload: dict, organization_id: int | None) -> None:
        captured_events.append((event_type, payload, organization_id))

    event_bus.subscribe(EventType.PATIENT_CREATED, capture_event)
    event_bus.subscribe(EventType.PATIENT_UPDATED, capture_event)
    try:
        create_response = patient_context["client"].post(
            "/api/v1/patients",
            json={
                "first_name": "Kamau",
                "last_name": "Otieno",
                "medical_record_number": "MRN-200",
                "date_of_birth": "1975-09-21",
            },
        )
        assert create_response.status_code == 201
        patient_id = create_response.json()["id"]

        update_response = patient_context["client"].put(
            f"/api/v1/patients/{patient_id}",
            json={"last_name": "Odhiambo"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["last_name"] == "Odhiambo"
    finally:
        event_bus.unsubscribe(EventType.PATIENT_CREATED, capture_event)
        event_bus.unsubscribe(EventType.PATIENT_UPDATED, capture_event)

    audit_actions = [
        entry.action
        for entry in patient_context["session"]
        .query(AuditLog)
        .filter(AuditLog.entity == "patient", AuditLog.entity_id == patient_id)
        .order_by(AuditLog.id)
        .all()
    ]
    assert audit_actions == ["patient.created", "patient.updated"]
    assert [event[0] for event in captured_events] == [
        "patient.created",
        "patient.updated",
    ]
    assert all(event[2] == patient_context["organization"].id for event in captured_events)
    assert all("first_name" not in event[1] for event in captured_events)
    assert all("date_of_birth" not in event[1] for event in captured_events)


def test_duplicate_medical_record_number_returns_conflict(patient_context) -> None:
    response = patient_context["client"].post(
        "/api/v1/patients",
        json={
            "first_name": "Another",
            "last_name": "Person",
            "medical_record_number": "MRN-100",
            "date_of_birth": "1985-01-01",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "medical_record_number already exists"


def test_cross_tenant_patient_is_hidden(patient_context) -> None:
    other_patient_id = (
        patient_context["session"]
        .query(Patient.id)
        .filter(Patient.organization_id == patient_context["other_organization"].id)
        .scalar()
    )

    response = patient_context["client"].get(f"/api/v1/patients/{other_patient_id}")

    assert response.status_code == 404


def test_cross_tenant_patient_cannot_be_updated(patient_context) -> None:
    other_patient = (
        patient_context["session"]
        .query(Patient)
        .filter(Patient.organization_id == patient_context["other_organization"].id)
        .one()
    )

    response = patient_context["client"].put(
        f"/api/v1/patients/{other_patient.id}",
        json={"last_name": "Changed"},
    )

    patient_context["session"].refresh(other_patient)
    assert response.status_code == 404
    assert other_patient.last_name == "Patient"


def test_patient_date_of_birth_cannot_be_in_the_future(patient_context) -> None:
    response = patient_context["client"].post(
        "/api/v1/patients",
        json={
            "first_name": "Future",
            "last_name": "Patient",
            "medical_record_number": "MRN-FUTURE",
            "date_of_birth": "2999-01-01",
        },
    )

    assert response.status_code == 422


def test_viewer_can_read_but_cannot_create_patient(patient_context) -> None:
    patient_context["user"].role = UserRole.VIEWER
    patient_context["session"].commit()

    list_response = patient_context["client"].get("/api/v1/patients")
    create_response = patient_context["client"].post(
        "/api/v1/patients",
        json={
            "first_name": "Blocked",
            "last_name": "Writer",
            "medical_record_number": "MRN-BLOCKED",
            "date_of_birth": "1991-01-01",
        },
    )

    assert list_response.status_code == 200
    assert create_response.status_code == 403
