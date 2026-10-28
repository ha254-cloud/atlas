"""
Unit tests for ClaimService — creation, updates, serialization, and the
immutable claim timeline (including the event_metadata persistence fix).
Uses an in-memory SQLite database — no real PostgreSQL required.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata
from app.claims.validators import (
    DuplicateClaimError,
    FutureServiceDateError,
    InvalidAmountError,
    InvalidPayerError,
    MissingPatientError,
    NegativeBalanceError,
)
from app.db.database import Base


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def seed(db):
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.user import User, UserRole

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    db.add(org)
    db.flush()

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
    db.add_all([patient, payer, user])
    db.commit()

    return {"org": org, "patient": patient, "payer": payer, "user": user}


@pytest.fixture()
def base_payload(seed):
    return {
        "patient_id": seed["patient"].id,
        "payer_id": seed["payer"].id,
        "claim_number": "CLM-0001",
        "billed_amount": 1500.00,
        "paid_amount": 0.00,
        "service_date": date(2026, 1, 5),
    }


def _service(db, seed):
    from app.claims.service import ClaimService

    return ClaimService(db, seed["org"].id)


def test_create_claim_persists_all_new_fields(db, seed, base_payload):
    service = _service(db, seed)
    payload = {
        **base_payload,
        "provider": "Dr. Jane Roe",
        "priority": "high",
        "assigned_user_id": seed["user"].id,
        "ai_risk_score": 82.5,
        "recovery_probability": 61.0,
    }

    result = service.create_claim(payload, actor_id=seed["user"].id)

    assert result["provider"] == "Dr. Jane Roe"
    assert result["priority"] == "high"
    assert result["assigned_user_id"] == seed["user"].id
    assert result["assigned_user_name"] == "Admin User"
    assert result["ai_risk_score"] == pytest.approx(82.5)
    assert result["recovery_probability"] == pytest.approx(61.0)


def test_create_claim_defaults_priority_to_medium(db, seed, base_payload):
    service = _service(db, seed)
    result = service.create_claim(base_payload, actor_id=seed["user"].id)
    assert result["priority"] == "medium"


def test_create_claim_records_timeline_event(db, seed, base_payload):
    service = _service(db, seed)
    result = service.create_claim(base_payload, actor_id=seed["user"].id)

    events = service.timeline.get_timeline(result["id"], seed["org"].id)
    # CREATED, then the workflow engine's auto IMPORTED->VALIDATED transition.
    assert len(events) == 2
    assert events[0].event_type.value == "claim.created"
    assert events[0].actor_id == seed["user"].id


def test_create_claim_rejects_duplicate_claim_number(db, seed, base_payload):
    service = _service(db, seed)
    service.create_claim(base_payload, actor_id=seed["user"].id)

    with pytest.raises(DuplicateClaimError):
        service.create_claim(base_payload, actor_id=seed["user"].id)


def test_create_claim_rejects_missing_patient(db, seed, base_payload):
    service = _service(db, seed)
    payload = {**base_payload, "patient_id": None}
    with pytest.raises(MissingPatientError):
        service.create_claim(payload)


def test_create_claim_rejects_missing_payer(db, seed, base_payload):
    service = _service(db, seed)
    payload = {**base_payload, "payer_id": None}
    with pytest.raises(InvalidPayerError):
        service.create_claim(payload)


def test_create_claim_rejects_negative_billed_amount(db, seed, base_payload):
    service = _service(db, seed)
    payload = {**base_payload, "billed_amount": -100}
    with pytest.raises(InvalidAmountError):
        service.create_claim(payload)


def test_create_claim_rejects_future_service_date(db, seed, base_payload):
    service = _service(db, seed)
    future = date.today() + timedelta(days=30)
    payload = {**base_payload, "service_date": future}
    with pytest.raises(FutureServiceDateError):
        service.create_claim(payload)


def test_create_claim_rejects_negative_balance(db, seed, base_payload):
    service = _service(db, seed)
    payload = {**base_payload, "billed_amount": 100.00, "paid_amount": 500.00}
    with pytest.raises(NegativeBalanceError):
        service.create_claim(payload)


def test_update_claim_status_change_records_timeline_event_with_metadata(db, seed, base_payload):
    service = _service(db, seed)
    created = service.create_claim(base_payload, actor_id=seed["user"].id)

    updated = service.update_claim(created["id"], {"status": "denied"}, actor_id=seed["user"].id)
    assert updated["status"] == "denied"

    events = service.timeline.get_timeline(created["id"], seed["org"].id)
    # CREATED, workflow auto-transition, then the manual status change.
    assert len(events) == 3
    status_event = events[-1]
    assert status_event.event_type.value == "claim.status_changed"
    # Regression guard for the event_metadata vs metadata attribute bug —
    # this must actually be persisted and readable, not silently dropped.
    assert status_event.event_metadata == {"from": "imported", "to": "denied"}


def test_update_claim_without_status_change_does_not_add_timeline_event(db, seed, base_payload):
    service = _service(db, seed)
    created = service.create_claim(base_payload, actor_id=seed["user"].id)

    service.update_claim(created["id"], {"provider": "Dr. New"}, actor_id=seed["user"].id)

    events = service.timeline.get_timeline(created["id"], seed["org"].id)
    # CREATED + the workflow engine's auto IMPORTED->VALIDATED transition
    # — still no *additional* event from this no-op status update.
    assert len(events) == 2


def test_update_claim_converts_priority_string_to_enum(db, seed, base_payload):
    from app.models.claim import ClaimPriority

    service = _service(db, seed)
    created = service.create_claim(base_payload, actor_id=seed["user"].id)

    service.update_claim(created["id"], {"priority": "critical"})

    claim = service.repo.get(created["id"])
    assert claim.priority == ClaimPriority.CRITICAL


def test_update_claim_returns_none_for_missing_claim(db, seed):
    service = _service(db, seed)
    assert service.update_claim(999999, {"status": "paid"}) is None


def test_list_claims_applies_filters(db, seed, base_payload):
    service = _service(db, seed)
    service.create_claim(base_payload, actor_id=seed["user"].id)
    service.create_claim(
        {**base_payload, "claim_number": "CLM-0002", "priority": "low"},
        actor_id=seed["user"].id,
    )

    results = service.list_claims(priority="low")
    assert len(results) == 1
    assert results[0]["priority"] == "low"


def test_delete_claim(db, seed, base_payload):
    service = _service(db, seed)
    created = service.create_claim(base_payload, actor_id=seed["user"].id)

    assert service.delete_claim(created["id"]) is True
    assert service.get_claim(created["id"]) is None
    assert service.delete_claim(created["id"]) is False
