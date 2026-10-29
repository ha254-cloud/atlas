from datetime import date, datetime
from decimal import Decimal

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
    attribution_version_id: int | None
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


class InvoiceCreditNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    invoice_id: int
    invoice_line_id: int
    payment_allocation_id: int | None
    attribution_resolution_id: int | None
    credit_note_number: str
    adjustment_type: str
    recovered_adjustment_amount: float
    fee_adjustment_amount: float
    vat_adjustment_amount: float
    total_credit_amount: float
    currency: str
    reason: str
    issued_by: int
    correlation_id: str
    issued_at: datetime


class InvoiceReconciliationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class InvoiceReconciliationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    invoice_id: int
    status: str
    source_payment_amount: Decimal
    expected_recovered_amount: Decimal
    actual_recovered_amount: Decimal
    expected_fee_amount: Decimal
    actual_fee_amount: Decimal
    expected_vat_amount: Decimal
    actual_vat_amount: Decimal
    credit_note_amount: Decimal
    expected_net_amount: Decimal
    actual_net_amount: Decimal
    discrepancy_amount: Decimal
    discrepancy_count: int
    currency: str
    details: dict
    run_by: int
    reason: str
    correlation_id: str
    created_at: datetime
