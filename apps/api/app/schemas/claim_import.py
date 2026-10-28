from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ClaimImport(BaseModel):
    claim_number: str

    patient_first_name: str
    patient_last_name: str

    payer_code: str

    billed_amount: Decimal

    paid_amount: Decimal

    service_date: date
