"""
Unit tests for ClaimRepository — org scoping, filtering, and search.
Uses an in-memory SQLite database — no real PostgreSQL required.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata
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

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    other_org = Organization(name="Other Clinic", email="other@example.com")
    db.add_all([org, other_org])
    db.flush()

    patient = Patient(
        organization_id=org.id,
        first_name="John",
        last_name="Smith",
        medical_record_number="MRN-001",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Aetna", payer_code="AETNA")
    db.add_all([patient, payer])
    db.flush()
    db.commit()

    return {"org": org, "other_org": other_org, "patient": patient, "payer": payer}


def _make_claim(db, seed, **overrides):
    from app.models.claim import Claim, ClaimPriority

    defaults = {
        "organization_id": seed["org"].id,
        "patient_id": seed["patient"].id,
        "payer_id": seed["payer"].id,
        "claim_number": f"CLM-{id(overrides)}-{overrides.get('claim_number', 'X')}",
        "status": "imported",
        "billed_amount": Decimal("1000.00"),
        "paid_amount": Decimal("0.00"),
        "service_date": date(2026, 1, 1),
        "priority": ClaimPriority.MEDIUM,
    }
    defaults.update(overrides)
    claim = Claim(**defaults)
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def test_list_scopes_by_organization(db, seed):
    from app.claims.repository import ClaimRepository
    from app.models.claim import ClaimPriority

    _make_claim(db, seed, claim_number="CLM-ORG1", priority=ClaimPriority.LOW)

    # A claim that belongs to a different organization must never surface.
    other_claim = _make_claim(
        db, seed, claim_number="CLM-ORG2", organization_id=seed["other_org"].id
    )

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list()

    assert len(results) == 1
    assert all(c.organization_id == seed["org"].id for c in results)
    assert other_claim.id not in [c.id for c in results]


def test_list_filters_by_status(db, seed):
    from app.claims.repository import ClaimRepository

    _make_claim(db, seed, claim_number="A", status="denied")
    _make_claim(db, seed, claim_number="B", status="paid")

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list(status="denied")

    assert len(results) == 1
    assert results[0].status == "denied"


def test_list_filters_by_priority(db, seed):
    from app.claims.repository import ClaimRepository
    from app.models.claim import ClaimPriority

    _make_claim(db, seed, claim_number="A", priority=ClaimPriority.HIGH)
    _make_claim(db, seed, claim_number="B", priority=ClaimPriority.LOW)

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list(priority="high")

    assert len(results) == 1
    assert results[0].priority == ClaimPriority.HIGH


def test_list_filters_by_payer(db, seed):
    from app.claims.repository import ClaimRepository
    from app.models.payer import Payer

    other_payer = Payer(organization_id=seed["org"].id, name="Medicare", payer_code="MCARE")
    db.add(other_payer)
    db.commit()

    _make_claim(db, seed, claim_number="A", payer_id=seed["payer"].id)
    _make_claim(db, seed, claim_number="B", payer_id=other_payer.id)

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list(payer_id=other_payer.id)

    assert len(results) == 1
    assert results[0].payer_id == other_payer.id


def test_list_filters_by_min_risk_score(db, seed):
    from app.claims.repository import ClaimRepository

    _make_claim(db, seed, claim_number="A", ai_risk_score=Decimal("90.00"))
    _make_claim(db, seed, claim_number="B", ai_risk_score=Decimal("10.00"))

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list(min_risk_score=50)

    assert len(results) == 1
    assert results[0].ai_risk_score == Decimal("90.00")


def test_list_filters_by_assigned_user(db, seed):
    from app.claims.repository import ClaimRepository
    from app.models.user import User, UserRole

    user = User(
        organization_id=seed["org"].id,
        email="biller@atlasdemo.com",
        password_hash="x",
        first_name="Bea",
        last_name="Biller",
        role=UserRole.BILLER,
    )
    db.add(user)
    db.commit()

    _make_claim(db, seed, claim_number="A", assigned_user_id=user.id)
    _make_claim(db, seed, claim_number="B")

    repo = ClaimRepository(db, seed["org"].id)
    results = repo.list(assigned_user_id=user.id)

    assert len(results) == 1
    assert results[0].assigned_user_id == user.id


def test_search_matches_claim_number_patient_or_payer(db, seed):
    from app.claims.repository import ClaimRepository

    _make_claim(db, seed, claim_number="CLM-SEARCHABLE")

    repo = ClaimRepository(db, seed["org"].id)

    assert len(repo.list(search="SEARCHABLE")) == 1
    assert len(repo.list(search="Smith")) == 1
    assert len(repo.list(search="Aetna")) == 1
    assert len(repo.list(search="nonexistent")) == 0


def test_get_by_claim_number(db, seed):
    from app.claims.repository import ClaimRepository

    claim = _make_claim(db, seed, claim_number="CLM-LOOKUP")

    repo = ClaimRepository(db, seed["org"].id)
    found = repo.get_by_claim_number(claim.claim_number)

    assert found is not None
    assert found.id == claim.id


def test_update_sets_fields(db, seed):
    from app.claims.repository import ClaimRepository

    claim = _make_claim(db, seed, claim_number="CLM-UPDATE")

    repo = ClaimRepository(db, seed["org"].id)
    updated = repo.update(claim.id, status="paid", provider="Dr. Roe")
    db.commit()

    assert updated.status == "paid"
    assert updated.provider == "Dr. Roe"


def test_delete_removes_claim(db, seed):
    from app.claims.repository import ClaimRepository

    claim = _make_claim(db, seed, claim_number="CLM-DELETE")

    repo = ClaimRepository(db, seed["org"].id)
    assert repo.delete(claim.id) is True
    db.commit()

    assert repo.get(claim.id) is None
    assert repo.delete(claim.id) is False
