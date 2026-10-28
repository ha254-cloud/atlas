from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.claim_decision import DecisionAction


class ClaimDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    decision_score: Decimal
    expected_roi: Decimal | None
    potential_recovery: Decimal
    estimated_effort_cost: Decimal
    recommended_action: DecisionAction
    reasoning: list[str]
    confidence: Decimal
    created_at: datetime


class DecisionQueueClaim(BaseModel):
    claim_id: int
    claim_number: str
    payer_name: str
    potential_recovery: float
    decision_score: float
    expected_roi: float | None
    confidence: float
    reasoning: list[str]


class DecisionQueueBucket(BaseModel):
    recommended_action: str
    total_potential_recovery: float
    count: int
    claims: list[DecisionQueueClaim]


class DecisionQueueResponse(BaseModel):
    buckets: list[DecisionQueueBucket]


class ExecutiveForecast(BaseModel):
    current_recoverable_revenue: float
    expected_recovery: float
    confidence: float
    average_time_days: float | None
    claims_evaluated: int


class PayerStatisticsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payer_id: int
    average_payment_time: float | None
    appeal_success_rate: float | None
    average_recovery: Decimal | None
    documentation_score: float | None
    average_denial_rate: float | None
    timely_filing_days: int | None
    sample_size: int
