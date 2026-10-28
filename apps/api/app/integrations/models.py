from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.canonical.claim import CanonicalClaim


@dataclass
class CanonicalPatient:
    """
    Atlas's internal representation of a patient.
    Every connector maps its vendor format into this structure.
    The import pipeline only ever sees CanonicalPatient — never raw vendor data.
    """

    first_name: str
    last_name: str
    date_of_birth: date
    medical_record_number: str
    external_id: str | None = None
    source_system: str | None = None
    raw: dict[str, Any] | None = field(default=None, repr=False)


@dataclass
class CanonicalPayment:
    """
    Atlas's internal representation of a payment / remittance.
    Maps from X12 835 or vendor payment APIs.
    """

    claim_number: str
    paid_amount: Decimal
    payment_date: date
    payer_code: str
    check_number: str | None = None
    adjustment_reason: str | None = None
    source_system: str | None = None
    raw: dict[str, Any] | None = field(default=None, repr=False)


@dataclass
class SyncResult:
    """Summary returned by every connector sync operation."""

    provider: str
    organization_id: int
    claims: list[CanonicalClaim] = field(default_factory=list)
    patients: list[CanonicalPatient] = field(default_factory=list)
    payments: list[CanonicalPayment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rejection_details: list[dict[str, Any]] = field(default_factory=list)
    synced_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
