from datetime import datetime
from decimal import Decimal

from app.canonical.claim import CanonicalClaim
from app.canonical.normalizers.base import BaseNormalizer


class CSVNormalizer(BaseNormalizer):
    """
    Maps a dict parsed from a CSV row into CanonicalClaim.
    Expected columns: claim_number, patient_first_name, patient_last_name,
    medical_record_number, payer_code, billed_amount, paid_amount, service_date.
    """

    def normalize(self, raw: dict) -> CanonicalClaim:
        service_date = raw.get("service_date")
        if isinstance(service_date, str):
            service_date = datetime.strptime(service_date, "%Y-%m-%d").date()

        authorization_expiration = raw.get("authorization_expiration")
        if isinstance(authorization_expiration, str) and authorization_expiration.strip():
            authorization_expiration = datetime.strptime(
                authorization_expiration.strip(), "%Y-%m-%d"
            ).date()
        else:
            authorization_expiration = None

        return CanonicalClaim(
            claim_number=raw["claim_number"].strip(),
            patient_mrn=raw.get("medical_record_number", "").strip(),
            payer_code=raw["payer_code"].strip(),
            billed_amount=Decimal(str(raw["billed_amount"])),
            paid_amount=Decimal(str(raw.get("paid_amount", 0))),
            service_date=service_date,
            patient_first_name=raw.get("patient_first_name", "").strip() or None,
            patient_last_name=raw.get("patient_last_name", "").strip() or None,
            diagnosis_codes=[
                c.strip() for c in raw.get("diagnosis_codes", "").split(",") if c.strip()
            ],
            procedure_codes=[
                c.strip() for c in raw.get("procedure_codes", "").split(",") if c.strip()
            ],
            modifiers=[m.strip() for m in raw.get("modifiers", "").split(",") if m.strip()],
            status=raw.get("status", "imported"),
            denial_code=raw.get("denial_code"),
            denial_reason=raw.get("denial_reason"),
            source_system="csv",
            branch_code=raw.get("branch_code", "").strip().upper() or None,
            department_code=raw.get("department_code", "").strip().upper() or None,
            currency=raw.get("currency", "").strip().upper() or None,
            authorization_number=raw.get("authorization_number", "").strip() or None
            if isinstance(raw.get("authorization_number"), str)
            else None,
            authorization_expiration=authorization_expiration,
        )
