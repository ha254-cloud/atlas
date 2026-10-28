from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.canonical.claim import CanonicalClaim
from app.processing.persistence import PersistenceLayer


def _claim(claim_number: str) -> CanonicalClaim:
    return CanonicalClaim(
        claim_number=claim_number,
        patient_mrn="",
        patient_first_name="Source",
        patient_last_name="Without MRN",
        payer_code="PAYER",
        billed_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 8, 3),
    )


def test_mrn_less_claims_receive_distinct_import_identifiers() -> None:
    persistence = PersistenceLayer(MagicMock(), organization_id=1)

    first = persistence.upsert_patient(_claim("CLM-NO-MRN-1"))
    second = persistence.upsert_patient(_claim("CLM-NO-MRN-2"))

    assert first.medical_record_number.startswith("IMP-")
    assert second.medical_record_number.startswith("IMP-")
    assert first.medical_record_number != second.medical_record_number
