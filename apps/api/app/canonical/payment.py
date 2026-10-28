from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class CanonicalPayment:
    claim_number: str
    paid_amount: Decimal
    payment_date: date
    payer_code: str
    check_number: str | None = None
    adjustment_reason: str | None = None
    source_system: str | None = None
