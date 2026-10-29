from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.recovery_attribution import (
    AttributionDisputeOutcome,
    AttributionStatus,
    InterventionType,
)


class RecoveryInterventionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: int
    submission_id: int | None = None
    intervention_type: InterventionType
    occurred_at: datetime
    reason: str = Field(min_length=3, max_length=500)


class RecoveryInterventionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    claim_id: int
    submission_id: int | None
    intervention_type: str
    occurred_at: datetime
    actor_id: int | None
    reason: str
    correlation_id: str | None
    created_at: datetime


class RecoveryAttributionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[AttributionStatus.ELIGIBLE, AttributionStatus.INELIGIBLE]
    intervention_id: int | None = None
    reason: str = Field(min_length=3, max_length=500)


class RecoveryAttributionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    recovery_id: int
    intervention_id: int | None
    previous_version_id: int | None
    version: int
    status: str
    evidence_state: str
    confirmed_amount: Decimal
    excluded_amount: Decimal
    reversal_amount: Decimal
    eligible_amount: Decimal
    fee_schedule_id: int
    fee_percentage: Decimal
    vat_percentage: Decimal
    currency: str
    payment_terms_days: int
    dispute_expires_at: datetime
    created_by: int
    reason: str
    correlation_id: str | None
    created_at: datetime


class RecoveryAttributionDisputeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class RecoveryAttributionDisputeResolutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: AttributionDisputeOutcome
    eligible_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    reason: str = Field(min_length=3, max_length=500)


class RecoveryAttributionDisputeResolutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    dispute_id: int
    outcome: str
    eligible_amount: Decimal
    resolved_by: int
    reason: str
    correlation_id: str
    resolved_at: datetime


class RecoveryAttributionDisputeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    recovery_id: int
    attribution_version_id: int
    opened_by: int
    reason: str
    correlation_id: str
    opened_at: datetime
    resolution: RecoveryAttributionDisputeResolutionRead | None


class RecoveryAttributionDisputeResolutionResultRead(BaseModel):
    resolution: RecoveryAttributionDisputeResolutionRead
    attribution: RecoveryAttributionRead
    credit_note_id: int | None


class RecoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    submission_id: int | None
    payment_id: int
    paid_amount: float
    expected_amount: float
    recovered_amount: float
    recovery_percentage: float
    atlas_fee_percentage: float
    atlas_fee_amount: float
    payment_date: date
    verified: bool
    verified_by: int | None
    verified_at: datetime | None
    verification_reason: str | None
    current_attribution: RecoveryAttributionRead | None


class RecoveryVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
