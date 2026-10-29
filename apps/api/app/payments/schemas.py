from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.payments.models import PaymentAllocationType, PaymentSource, PaymentStatus


class PaymentIngest(BaseModel):
    claim_id: int | None = None
    submission_id: int | None = None
    payer_name: str = Field(min_length=1, max_length=255)
    payment_reference: str = Field(min_length=1, max_length=255)
    payment_date: date
    expected_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    paid_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    adjustment_amount: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    payment_method: str | None = Field(default=None, max_length=50)
    status: PaymentStatus
    source: PaymentSource
    raw_payload: dict

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PaymentMatch(BaseModel):
    claim_id: int
    submission_id: int | None = None
    reason: str = Field(min_length=1, max_length=500)


class PaymentMatchCandidate(BaseModel):
    claim_id: int
    claim_number: str
    payer_name: str
    billed_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    currency: str
    confidence: int
    reasons: list[str]


class SettlementEvidenceCreate(BaseModel):
    evidence_type: Literal[
        "bank_statement",
        "payer_remittance",
        "portal_export",
        "settlement_report",
        "source_record",
    ]
    settlement_reference: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    received_at: datetime
    source_hash: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=100)

    @field_validator("currency")
    @classmethod
    def normalize_evidence_currency(cls, value: str) -> str:
        return value.upper()


class SettlementEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    payment_id: int
    evidence_type: str
    settlement_reference: str
    amount: Decimal
    currency: str
    received_at: datetime
    source_hash: str
    actor_id: int | None
    reason: str
    correlation_id: str
    idempotency_key: str
    created_at: datetime


class PaymentAllocationItem(BaseModel):
    claim_id: int
    submission_id: int | None = None
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class PaymentAllocationBatchCreate(BaseModel):
    allocations: list[PaymentAllocationItem] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=80)


class PaymentAllocationAdjustmentCreate(BaseModel):
    adjustment_type: Literal[
        PaymentAllocationType.REVERSAL,
        PaymentAllocationType.REFUND,
    ]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=100)


class PaymentAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    payment_id: int
    claim_id: int
    submission_id: int | None
    parent_allocation_id: int | None
    allocation_type: str
    amount: Decimal
    currency: str
    actor_id: int | None
    actor_type: str
    reason: str
    correlation_id: str
    idempotency_key: str
    item_index: int
    created_at: datetime


class PaymentAllocationBatchRead(BaseModel):
    allocations: list[PaymentAllocationRead]
    created: bool
    allocated_amount: Decimal
    unallocated_amount: Decimal


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    claim_id: int | None
    submission_id: int | None
    payer_name: str
    payment_reference: str
    payment_date: date
    expected_amount: Decimal
    paid_amount: Decimal
    adjustment_amount: Decimal
    currency: str
    payment_terms_days: int
    payment_method: str | None
    status: PaymentStatus
    source: PaymentSource
    raw_payload: dict
    matched_at: datetime | None
    matched_by_id: int | None
    matching_method: str | None
    matching_reason: str | None
    correlation_id: str
    created_at: datetime
    allocated_amount: Decimal
    unallocated_amount: Decimal


class RecoveryFeeScheduleCreate(BaseModel):
    fee_percentage: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    vat_percentage: Decimal = Field(
        default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2
    )
    currency: str = Field(min_length=3, max_length=3)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    dispute_period_days: int = Field(default=0, ge=0, le=365)
    effective_from: date
    effective_to: date | None = None
    reason: str = Field(min_length=1, max_length=500)


class RecoveryFeeScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    fee_percentage: Decimal
    vat_percentage: Decimal
    currency: str
    payment_terms_days: int
    dispute_period_days: int
    effective_from: date
    effective_to: date | None
    created_by: int | None
    reason: str
    created_at: datetime


class PaymentTrackingStage(BaseModel):
    key: str
    label: str
    state: str
    detail: str | None = None
    occurred_at: datetime | None = None


class ClaimPaymentTrackingRead(BaseModel):
    claim_id: int
    stages: list[PaymentTrackingStage]
    appeal_id: int | None
    appeal_status: str | None
    submission_id: int | None
    submission_status: str | None
    submission_channel: str | None
    payment_received: bool
    payment_amount: Decimal | None
    payment_currency: str | None
    payment_received_at: datetime | None
    recovery_verified: bool
    recovered_amount: Decimal | None
    atlas_fee_amount: Decimal | None
    recovery_verified_at: datetime | None
    invoice_created: bool
    invoice_id: int | None
    invoice_number: str | None
    invoice_status: str | None
    last_updated_at: datetime | None
