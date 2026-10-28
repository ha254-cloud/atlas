"""
Tests for the standalone `scripts/seed_denial_codes.py` reseed helper —
verifies it upserts every entry in DENIAL_CODE_SEED_DATA idempotently
(insert once, then update on rerun without creating duplicates).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_seed_denial_codes_creates_every_seed_entry(db):
    from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA
    from app.models.denial_code import DenialCode
    from scripts.seed_denial_codes import seed_denial_codes

    created, updated = seed_denial_codes(db)

    assert created == len(DENIAL_CODE_SEED_DATA)
    assert updated == 0
    assert db.query(DenialCode).count() == len(DENIAL_CODE_SEED_DATA)


def test_seed_denial_codes_is_idempotent_on_rerun(db):
    from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA
    from app.models.denial_code import DenialCode
    from scripts.seed_denial_codes import seed_denial_codes

    seed_denial_codes(db)
    created, updated = seed_denial_codes(db)

    assert created == 0
    assert updated == len(DENIAL_CODE_SEED_DATA)
    assert db.query(DenialCode).count() == len(DENIAL_CODE_SEED_DATA)


def test_seed_denial_codes_populates_ai_guidance_and_category(db):
    from app.models.denial import DenialType
    from app.models.denial_code import DenialCode, DenialCodeRecoverability, DenialCodeSeverity
    from scripts.seed_denial_codes import seed_denial_codes

    seed_denial_codes(db)

    co29 = db.query(DenialCode).filter(DenialCode.code == "CO29").first()
    assert co29.category == DenialType.TIMELY_FILING
    assert co29.ai_guidance is not None
    assert co29.is_active is True
    assert co29.severity == DenialCodeSeverity.HIGH
    assert co29.recoverability == DenialCodeRecoverability.LOW
    assert co29.typical_recovery_rate == 25.0
    assert co29.required_documents == [
        "Clearinghouse acceptance report",
        "Proof of original timely submission",
    ]
    assert co29.typical_resolution_days == 30
    assert co29.common_payers == []
    assert co29.references == ["X12 Claim Adjustment Reason Code (CARC) official code list"]


def test_seed_catalog_has_no_unsourced_payer_affinities():
    from app.ai.denial_code_seed_data import DENIAL_CODE_SEED_DATA

    assert all(entry["common_payers"] == [] for entry in DENIAL_CODE_SEED_DATA)
