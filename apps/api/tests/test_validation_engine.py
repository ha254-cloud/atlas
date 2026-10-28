"""
Unit tests for the pre-submission ValidationEngine rules.
Pure unit tests — no database required.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.canonical.claim import CanonicalClaim
from app.validation.engine import ValidationEngine


def make_claim(**overrides) -> CanonicalClaim:
    defaults = {
        "claim_number": "CLM-VAL-001",
        "patient_mrn": "MRN-1",
        "payer_code": "BCBS",
        "billed_amount": Decimal("100.00"),
        "paid_amount": Decimal("0.00"),
        "service_date": date(2026, 1, 10),
        "diagnosis_codes": ["E11.9"],
        "procedure_codes": ["99213"],
        "modifiers": ["25"],
    }
    defaults.update(overrides)
    return CanonicalClaim(**defaults)


def test_valid_claim_has_no_blocking_issues():
    engine = ValidationEngine()
    claim = make_claim()
    issues = engine.run(claim)
    assert engine.blocking_issues(issues) == []


def test_zero_billed_amount_is_blocking():
    engine = ValidationEngine()
    claim = make_claim(billed_amount=Decimal("0.00"))
    issues = engine.run(claim)
    codes = [i.code for i in engine.blocking_issues(issues)]
    assert "INVALID_BILLED_AMOUNT" in codes


def test_overpayment_is_a_warning_not_blocking():
    engine = ValidationEngine()
    claim = make_claim(billed_amount=Decimal("100.00"), paid_amount=Decimal("150.00"))
    issues = engine.run(claim)
    assert engine.blocking_issues(issues) == []
    codes = [i.code for i in engine.warnings(issues)]
    assert "OVERPAYMENT" in codes


def test_invalid_cpt_format_is_blocking():
    engine = ValidationEngine()
    claim = make_claim(procedure_codes=["ABC12"])
    issues = engine.run(claim)
    codes = [i.code for i in engine.blocking_issues(issues)]
    assert "INVALID_CPT_FORMAT" in codes


def test_invalid_icd10_format_is_blocking():
    engine = ValidationEngine()
    claim = make_claim(diagnosis_codes=["12345"])
    issues = engine.run(claim)
    codes = [i.code for i in engine.blocking_issues(issues)]
    assert "INVALID_ICD10_FORMAT" in codes


def test_missing_modifier_on_flagged_cpt_is_a_warning():
    engine = ValidationEngine()
    claim = make_claim(procedure_codes=["99213"], modifiers=[])
    issues = engine.run(claim)
    assert engine.blocking_issues(issues) == []
    codes = [i.code for i in engine.warnings(issues)]
    assert "MISSING_MODIFIER" in codes


def test_missing_diagnosis_is_a_warning_not_blocking():
    engine = ValidationEngine()
    claim = make_claim(diagnosis_codes=[])
    issues = engine.run(claim)
    assert engine.blocking_issues(issues) == []
    codes = [i.code for i in engine.warnings(issues)]
    assert "MISSING_DIAGNOSIS" in codes


def test_expired_authorization_is_blocking():
    engine = ValidationEngine()
    claim = make_claim(
        service_date=date(2026, 1, 10),
        authorization_expiration=date(2026, 1, 1),
    )
    issues = engine.run(claim)
    codes = [i.code for i in engine.blocking_issues(issues)]
    assert "AUTHORIZATION_EXPIRED" in codes


def test_valid_authorization_does_not_block():
    engine = ValidationEngine()
    claim = make_claim(
        service_date=date(2026, 1, 10),
        authorization_expiration=date(2026, 6, 1),
    )
    issues = engine.run(claim)
    assert engine.blocking_issues(issues) == []


def test_stale_service_date_is_a_timely_filing_warning():
    old_date = date(2026, 1, 1) - timedelta(days=400)
    claim = make_claim(service_date=old_date)
    from app.validation.rules import check_timely_filing

    issues = check_timely_filing(claim, today=date(2026, 1, 1))
    codes = [i.code for i in issues]
    assert "TIMELY_FILING_RISK" in codes


def test_missing_payer_code_is_blocking():
    engine = ValidationEngine()
    claim = make_claim(payer_code="")
    issues = engine.run(claim)
    codes = [i.code for i in engine.blocking_issues(issues)]
    assert "MISSING_PAYER_CODE" in codes
