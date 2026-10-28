from app.canonical.claim import CanonicalClaim
from app.canonical.normalizers.base import BaseNormalizer


class FHIRNormalizer(BaseNormalizer):
    """
    Maps a FHIR R4 ExplanationOfBenefit resource dict into CanonicalClaim.
    Full implementation deferred to FHIR sprint.

    FHIR EOB key paths:
      identifier[?system=claim_number].value  → claim_number
      patient.reference                        → patient_mrn
      insurer.identifier.value                 → payer_code
      total[?category=submitted].amount.value  → billed_amount
      total[?category=benefit].amount.value    → paid_amount
      billablePeriod.start                     → service_date
      diagnosis[].diagnosisCodeableConcept     → diagnosis_codes
      item[].productOrService                  → procedure_codes
      item[].modifier                          → modifiers
    """

    def normalize(self, raw: dict) -> CanonicalClaim:
        raise NotImplementedError("FHIR normalizer — coming in FHIR sprint")
