"""
Integration tests for the ClaimProcessor end-to-end pipeline.
Uses an in-memory SQLite database — no real PostgreSQL required.
"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.db.database import Base
from app.imports.parser import CSVParser


def test_csv_parser_accepts_utf8_bom(tmp_path):
    csv_path = tmp_path / "bom-claims.csv"
    csv_path.write_bytes(b"\xef\xbb\xbfclaim_number,status\r\nCLM-BOM-001,denied\r\n")

    parser = CSVParser()

    assert parser.get_headers(str(csv_path)) == ["claim_number", "status"]
    assert list(parser.parse(str(csv_path))) == [
        {"claim_number": "CLM-BOM-001", "status": "denied"}
    ]
    assert parser.count_rows(str(csv_path)) == 1


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def org_id():
    return 1


@pytest.fixture
def valid_row():
    return {
        "claim_number": "CLM-TEST-001",
        "medical_record_number": "MRN-TEST-001",
        "payer_code": "BCBS",
        "billed_amount": "3000.00",
        "paid_amount": "0.00",
        "service_date": "2026-01-10",
        "status": "denied",
    }


def test_processor_creates_claim(db, org_id, valid_row):
    from app.processing.processor import ClaimProcessor

    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    assert claim.id is not None
    assert claim.claim_number == "CLM-TEST-001"
    assert claim.organization_id == org_id
    assert claim.billed_amount == Decimal("3000.00")


def test_processor_creates_recovery_case(db, org_id, valid_row):
    from app.models.recovery_case import RecoveryCase
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-002"
    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    rc = db.query(RecoveryCase).filter(RecoveryCase.claim_id == claim.id).first()
    assert rc is not None
    assert rc.status.value == "open"
    assert rc.estimated_value > 0


def test_processor_raises_on_missing_required_field(db, org_id):
    from app.processing.exceptions import ValidationError
    from app.processing.processor import ClaimProcessor

    processor = ClaimProcessor(db, org_id)
    with pytest.raises(ValidationError):
        processor.process({"claim_number": "CLM-BAD"})  # missing required fields


def test_processor_raises_on_duplicate_claim_number(db, org_id, valid_row):
    from app.processing.exceptions import DuplicateClaimError
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-003"
    processor = ClaimProcessor(db, org_id)
    processor.process(valid_row)

    with pytest.raises(DuplicateClaimError):
        ClaimProcessor(db, org_id).process(valid_row)


def test_normalizer_captures_patient_name():
    from app.canonical.normalizers.csv import CSVNormalizer

    row = {
        "claim_number": "CLM-TEST-004",
        "payer_code": "BCBS",
        "billed_amount": "100.00",
        "paid_amount": "0.00",
        "service_date": "2026-01-10",
        "patient_first_name": " Jane ",
        "patient_last_name": " Doe ",
    }
    canonical = CSVNormalizer().normalize(row)

    assert canonical.patient_first_name == "Jane"
    assert canonical.patient_last_name == "Doe"


def test_processor_records_claim_imported_event(db, org_id, valid_row):
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-005"
    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    event = (
        db.query(ClaimEvent)
        .filter(ClaimEvent.claim_id == claim.id, ClaimEvent.organization_id == org_id)
        .first()
    )
    assert event is not None
    assert event.event_type == ClaimEventType.IMPORTED


def test_processor_raises_on_invalid_cpt_format(db, org_id, valid_row):
    from app.models.claim import Claim
    from app.processing.exceptions import ClaimValidationError
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-006"
    valid_row["procedure_codes"] = "1234"  # not a valid 5-digit CPT code
    processor = ClaimProcessor(db, org_id)

    with pytest.raises(ClaimValidationError):
        processor.process(valid_row)

    claim = db.query(Claim).filter(Claim.claim_number == "CLM-TEST-006").first()
    assert claim is None


def test_processor_persists_validation_warnings(db, org_id, valid_row):
    from app.models.claim_validation_issue import ClaimValidationIssue
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-007"
    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    issues = db.query(ClaimValidationIssue).filter(ClaimValidationIssue.claim_id == claim.id).all()
    codes = [i.code for i in issues]
    # valid_row has no diagnosis_codes column, which the validation engine
    # flags as a (non-blocking) warning rather than rejecting the claim.
    assert "MISSING_DIAGNOSIS" in codes


def test_processor_persists_denial_when_source_provides_one(db, org_id, valid_row):
    from app.models.claim_event import ClaimEvent, ClaimEventType
    from app.models.denial import Denial, DenialType
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-008"
    valid_row["denial_code"] = "CO-97"
    valid_row["denial_reason"] = "Payment included in another allowance."
    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    denial = db.query(Denial).filter(Denial.claim_id == claim.id).first()
    assert denial is not None
    assert denial.denial_code == "CO-97"
    assert denial.description == "Payment included in another allowance."
    assert denial.denial_type == DenialType.OTHER

    event = (
        db.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == claim.id, ClaimEvent.event_type == ClaimEventType.DENIAL_RECORDED
        )
        .first()
    )
    assert event is not None


def test_processor_skips_denial_when_source_has_none(db, org_id, valid_row):
    from app.models.denial import Denial
    from app.processing.processor import ClaimProcessor

    valid_row["claim_number"] = "CLM-TEST-009"
    processor = ClaimProcessor(db, org_id)
    claim = processor.process(valid_row)

    denial = db.query(Denial).filter(Denial.claim_id == claim.id).first()
    assert denial is None
