from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class CanonicalClaim:
    """
    Atlas's internal canonical representation of a claim.

    Every data source — CSV, FHIR, X12, REST API — must map into this
    structure before entering the import pipeline.  No downstream code
    ever sees raw vendor payloads.
    """

    claim_number: str
    patient_mrn: str
    payer_code: str
    billed_amount: Decimal
    paid_amount: Decimal
    service_date: date

    # Populated by FHIR / X12 sources; optional for CSV
    provider_npi: str | None = None
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    diagnosis_codes: list[str] = field(default_factory=list)
    procedure_codes: list[str] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)

    status: str = "imported"
    denial_code: str | None = None
    denial_reason: str | None = None
    external_id: str | None = None
    source_system: str | None = None
    branch_code: str | None = None
    department_code: str | None = None
    currency: str | None = None

    # Optional prior-authorization data — only present when the source
    # system tracks it (e.g. CSV columns authorization_number/
    # authorization_expiration). Used by the validation engine to flag
    # claims billed after their authorization lapsed.
    authorization_number: str | None = None
    authorization_expiration: date | None = None
