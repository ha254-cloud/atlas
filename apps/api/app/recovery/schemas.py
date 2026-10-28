from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.recovery.models import RecoveryEventType, RecoveryLifecycleState


class RecoveryOpportunity(BaseModel):
    id: int
    claim_id: int
    claim_number: str
    payer_id: int
    patient_id: int
    recovery_score: float
    estimated_value: float
    status: str
    priority: str
    recommendation: str
    billed_amount: float
    paid_amount: float
    balance: float
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class RecoveryListResponse(BaseModel):
    items: list[RecoveryOpportunity]
    total: int
    limit: int
    offset: int


class LifecycleTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_state: RecoveryLifecycleState
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=255)


class RecoveryAccountOpenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class FinancialAllocationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocation_type: Literal["contract_adjustment", "write_off", "write_off_reversal"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason_code: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=255)


class ResponsibilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_user_id: int | None
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=255)


class RecoveryAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    claim_id: int
    currency: str
    state: RecoveryLifecycleState
    assigned_user_id: int | None
    version: int
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FinancialPositionRead(BaseModel):
    claim_id: int
    account_id: int
    currency: str
    original_amount: Decimal
    recovered_amount: Decimal
    outstanding_amount: Decimal
    recoverable_amount: Decimal
    expected_recovery_amount: Decimal
    contract_adjustment_amount: Decimal
    written_off_amount: Decimal
    recovery_probability_pct: Decimal
    fully_accounted: bool
    as_of: datetime


class RecoveryOpportunityRead(BaseModel):
    claim_id: int
    account_id: int
    outstanding_amount: Decimal
    recovery_probability_pct: Decimal
    expected_recovery_amount: Decimal
    estimated_cost_to_recover: Decimal
    expected_net_benefit: Decimal
    priority: Literal["critical", "high", "medium", "low"]
    recommendation: Literal[
        "appeal_immediately", "pursue", "monitor", "consider_write_off", "close"
    ]
    rationale: str


class LifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    event_type: RecoveryEventType
    from_state: RecoveryLifecycleState | None
    to_state: RecoveryLifecycleState
    amount: Decimal | None
    currency: str
    reason_code: str | None
    reason: str
    actor_id: int | None
    actor_type: str
    source_type: str | None
    source_id: int | None
    occurred_at: datetime
    event_metadata: dict


class RecoveryLifecycleRead(BaseModel):
    account: RecoveryAccountRead
    position: FinancialPositionRead
    opportunity: RecoveryOpportunityRead
    events: list[LifecycleEventRead]


class ForecastBucketRead(BaseModel):
    start_date: date
    end_date: date
    expected_amount: Decimal


class RecoveryForecastRead(BaseModel):
    currency: str
    outstanding_amount: Decimal
    expected_recovery_amount: Decimal
    expected_collection_days: float
    confidence_pct: Decimal
    buckets: list[ForecastBucketRead]
    as_of: datetime


class RecoveryPortfolioRead(BaseModel):
    currency: str
    original_amount: Decimal
    recovered_amount: Decimal
    outstanding_amount: Decimal
    recoverable_amount: Decimal
    expected_recovery_amount: Decimal
    high_probability_amount: Decimal
    medium_probability_amount: Decimal
    low_probability_amount: Decimal
    recoverable_revenue_index_pct: Decimal
    atlas_recoveries: Decimal
    atlas_fees: Decimal
    return_on_investment_pct: Decimal | None
    account_count: int
    as_of: datetime


class BillingReadinessRead(BaseModel):
    currency: str
    verified_uninvoiced_recovery_count: int
    recovered_amount: Decimal
    atlas_fee_amount: Decimal
    ready: bool
