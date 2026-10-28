from app.canonical.claim import CanonicalClaim
from app.canonical.normalizers.base import BaseNormalizer


class X12Normalizer(BaseNormalizer):
    """
    Maps a parsed X12 837 transaction dict into CanonicalClaim.
    Full implementation deferred to clearinghouse sprint.

    X12 837 key segments:
      CLM01  → claim_number
      NM1*IL → patient identifiers / MRN
      NM1*PR → payer identifier
      CLM02  → billed_amount
      SVC02  → paid_amount (from 835 response)
      DTP*472 → service_date
      HI     → diagnosis_codes (ICD-10)
      SV1/SV2 → procedure_codes (CPT/HCPCS) + modifiers
    """

    def normalize(self, raw: dict) -> CanonicalClaim:
        raise NotImplementedError("X12 normalizer — coming in clearinghouse sprint")
