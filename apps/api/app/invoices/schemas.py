from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.invoice import InvoiceStatus


class InvoicePeriodRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recovery_id: int
    payment_id: int
    claim_id: int
    payment_date: date
    recovered_amount: float
    fee_percentage: float
    fee_amount: float


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    period_start: date
    period_end: date
    status: InvoiceStatus
    total_recovered_amount: float
    total_fee_amount: float
    vat_percentage: float
    vat_amount: float
    total_amount: float
    currency: str
    payment_terms_days: int
    due_date: date
    billing_name: str
    billing_email: str
    pdf_generated_at: datetime | None
    sent_at: datetime | None
    paid_at: datetime | None
    lines: list[InvoiceLineRead]
