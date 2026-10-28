"""
Unit tests for the CSV normalizer.
Tests real normalizer behaviour — no mocks.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.canonical.normalizers.csv import CSVNormalizer


@pytest.fixture
def normalizer():
    return CSVNormalizer()


@pytest.fixture
def valid_row():
    return {
        "claim_number": "CLM-001",
        "medical_record_number": "MRN-001",
        "payer_code": "BCBS",
        "billed_amount": "1500.00",
        "paid_amount": "1200.00",
        "service_date": "2026-03-15",
        "diagnosis_codes": "Z00.00, J06.9",
        "procedure_codes": "99213, 87880",
        "modifiers": "25",
        "status": "paid",
    }


def test_normalize_produces_canonical_claim(normalizer, valid_row):
    result = normalizer.normalize(valid_row)
    assert result.claim_number == "CLM-001"
    assert result.payer_code == "BCBS"
    assert result.billed_amount == Decimal("1500.00")
    assert result.paid_amount == Decimal("1200.00")
    assert result.service_date == date(2026, 3, 15)


def test_normalize_parses_diagnosis_codes(normalizer, valid_row):
    result = normalizer.normalize(valid_row)
    assert "Z00.00" in result.diagnosis_codes
    assert "J06.9" in result.diagnosis_codes


def test_normalize_parses_procedure_codes(normalizer, valid_row):
    result = normalizer.normalize(valid_row)
    assert "99213" in result.procedure_codes
    assert "87880" in result.procedure_codes


def test_normalize_empty_codes_return_empty_lists(normalizer, valid_row):
    valid_row.pop("diagnosis_codes", None)
    valid_row.pop("procedure_codes", None)
    result = normalizer.normalize(valid_row)
    assert result.diagnosis_codes == []
    assert result.procedure_codes == []


def test_normalize_strips_whitespace(normalizer, valid_row):
    valid_row["claim_number"] = "  CLM-001  "
    valid_row["payer_code"] = " BCBS "
    result = normalizer.normalize(valid_row)
    assert result.claim_number == "CLM-001"
    assert result.payer_code == "BCBS"


def test_normalize_zero_paid_amount(normalizer, valid_row):
    valid_row["paid_amount"] = "0"
    valid_row["status"] = "denied"
    result = normalizer.normalize(valid_row)
    assert result.paid_amount == Decimal("0")
    assert result.status == "denied"


def test_normalize_sets_source_system(normalizer, valid_row):
    result = normalizer.normalize(valid_row)
    assert result.source_system == "csv"
